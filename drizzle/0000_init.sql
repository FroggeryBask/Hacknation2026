CREATE TABLE "notes" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"user_id" uuid DEFAULT auth.uid() NOT NULL,
	"content" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "notes" ENABLE ROW LEVEL SECURITY;--> statement-breakpoint
ALTER TABLE "notes" ADD CONSTRAINT "notes_user_id_users_id_fk" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE POLICY "notes_select_own" ON "notes" AS PERMISSIVE FOR SELECT TO "authenticated" USING ((select auth.uid()) = "notes"."user_id");--> statement-breakpoint
CREATE POLICY "notes_insert_own" ON "notes" AS PERMISSIVE FOR INSERT TO "authenticated" WITH CHECK ((select auth.uid()) = "notes"."user_id");--> statement-breakpoint
CREATE POLICY "notes_update_own" ON "notes" AS PERMISSIVE FOR UPDATE TO "authenticated" USING ((select auth.uid()) = "notes"."user_id") WITH CHECK ((select auth.uid()) = "notes"."user_id");--> statement-breakpoint
CREATE POLICY "notes_delete_own" ON "notes" AS PERMISSIVE FOR DELETE TO "authenticated" USING ((select auth.uid()) = "notes"."user_id");