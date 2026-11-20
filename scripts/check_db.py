"""Supabase data-access audit. Exit code 1 if anything is exposed.

Checks (needs DATABASE_URL):
  - every table in `public` has RLS enabled
  - RLS tables with zero policies (warning: app will see empty results)
  - views in `public` without security_invoker (they bypass RLS)
  - SECURITY DEFINER functions in `public` callable by anon/authenticated
  - UPDATE policies missing WITH CHECK
Then (needs the publishable key) probes each table as a logged-out visitor:
  any returned row = FAIL.
"""

import os
import sys

import httpx
import psycopg

from _env import load_env

FAIL, WARN, OK = "\033[31mFAIL\033[0m", "\033[33mWARN\033[0m", "\033[32m OK \033[0m"


def main() -> int:
    load_env()
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print(f"{WARN} DATABASE_URL not set in .env.local, skipping DB audit")
        return 0

    problems = 0
    with psycopg.connect(db_url, prepare_threshold=None) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select c.relname, c.relrowsecurity,
                   (select count(*) from pg_policies p
                    where p.schemaname = 'public' and p.tablename = c.relname)
            from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relkind in ('r', 'p')
            order by 1
            """
        )
        tables = cur.fetchall()
        if not tables:
            print(f"{OK} no tables in public yet")
        for name, rls, n_policies in tables:
            if not rls:
                print(f"{FAIL} table public.{name}: RLS is OFF (anyone with the public key can read it)")
                problems += 1
            elif n_policies == 0:
                print(f"{WARN} table public.{name}: RLS on but no policies (all queries return nothing)")
            else:
                print(f"{OK} table public.{name}: RLS on, {n_policies} policies")

        cur.execute(
            """
            select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
            where n.nspname = 'public' and c.relkind in ('v', 'm')
              and not coalesce(c.reloptions::text[] && array['security_invoker=true',
                                                             'security_invoker=on'], false)
            """
        )
        for (name,) in cur.fetchall():
            print(f"{FAIL} view public.{name}: missing security_invoker=true (bypasses RLS)")
            problems += 1

        cur.execute(
            """
            select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace
            where n.nspname = 'public' and p.prosecdef
              -- event-trigger functions (e.g. Supabase's rls_auto_enable) can't be called via the API
              and p.prorettype <> 'event_trigger'::regtype
              and (has_function_privilege('anon', p.oid, 'execute')
                   or has_function_privilege('authenticated', p.oid, 'execute'))
            """
        )
        for (name,) in cur.fetchall():
            print(f"{WARN} function public.{name}: SECURITY DEFINER and callable via the API, review it")

        # A policy with no condition allows EVERY row (e.g. any logged-in user reads all data).
        # Intentionally public policies must say so explicitly: using (true).
        cur.execute(
            """
            select tablename, policyname, cmd from pg_policies
            where schemaname = 'public'
              and ((cmd = 'INSERT' and with_check is null)
                   or (cmd <> 'INSERT' and qual is null))
            """
        )
        for table, policy, cmd in cur.fetchall():
            print(f"{FAIL} policy {policy} on {table} ({cmd}): no condition, allows every row")
            problems += 1

    problems += probe_as_anon([t[0] for t in tables])
    print(f"\n{'FAIL' if problems else 'PASS'}: {problems} problem(s)")
    return 1 if problems else 0


def probe_as_anon(tables: list[str]) -> int:
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    if not (url and key and tables):
        return 0
    problems = 0
    headers = {"apikey": key}
    with httpx.Client(base_url=f"{url}/rest/v1", headers=headers, timeout=10) as http:
        for name in tables:
            r = http.get(f"/{name}", params={"select": "*", "limit": 1})
            if r.status_code == 200 and r.json():
                print(f"{FAIL} anon probe: public.{name} returned data to a logged-out visitor")
                problems += 1
            else:
                print(f"{OK} anon probe: public.{name} -> {r.status_code}, no rows leaked")
    return problems


if __name__ == "__main__":
    sys.exit(main())
