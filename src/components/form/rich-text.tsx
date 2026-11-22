"use client";

import { Fragment, type ReactNode, useSyncExternalStore } from "react";
import { ClauseLink, isClauseLink } from "./clause";
import { ExternalLinkText } from "./fields";

/*
 * HTML from the JSON `description` (rich text editor output) → React.
 * Allowlist only: inline styles, images and unknown tags are dropped, so the
 * text always uses the design-system tokens. Never uses innerHTML.
 */

const BLOCK: Record<string, string> = {
  p: "",
  ul: "list-disc pl-5 [&>li+li]:mt-1",
  ol: "list-decimal pl-5 [&>li+li]:mt-1",
  li: "",
};

function convert(node: ChildNode, key: number, inline: boolean): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (node.nodeType !== Node.ELEMENT_NODE) return null;
  const el = node as Element;
  const tag = el.tagName.toLowerCase();
  const children = Array.from(el.childNodes).map((c, i) =>
    convert(c, i, inline),
  );
  switch (tag) {
    case "p":
    case "ul":
    case "ol":
    case "li": {
      // Inside a <p> (field description) blocks become block-level spans.
      const Tag = inline ? "span" : tag;
      const block = inline ? "block " : "";
      return (
        <Tag key={key} className={block + BLOCK[tag] || undefined}>
          {children}
        </Tag>
      );
    }
    case "strong":
    case "b":
      return <strong key={key}>{children}</strong>;
    case "em":
    case "i":
      return <em key={key}>{children}</em>;
    case "u":
      return <u key={key}>{children}</u>;
    case "br":
      return <br key={key} />;
    case "a": {
      const href = el.getAttribute("href")?.trim() ?? "";
      const text = el.textContent?.trim();
      if (!text) return null; // icon-only anchors (img) from the editor
      if (isClauseLink(href)) return <ClauseLink key={key}>{text}</ClauseLink>;
      return /^https?:\/\//.test(href) ? (
        <ExternalLinkText key={key} href={href}>
          {text}
        </ExternalLinkText>
      ) : (
        <strong key={key}>{text}</strong>
      );
    }
    case "img":
    case "script":
    case "style":
    case "head":
      return null;
    default:
      return <Fragment key={key}>{children}</Fragment>;
  }
}

const noop = () => () => {};

/** True when the HTML has visible text (the editor emits empty `<html>` shells). */
export const hasText = (html?: string | null) =>
  !!html && html.replace(/<[^>]*>|&nbsp;/g, "").trim().length > 0;

export function RichText({
  html,
  inline = false,
}: {
  html?: string | null;
  /** Rendered inside phrasing content (e.g. FieldDescription <p>). */
  inline?: boolean;
}) {
  // DOMParser exists only in the browser; render after hydration.
  const client = useSyncExternalStore(
    noop,
    () => true,
    () => false,
  );
  if (!hasText(html) || !client) return null;
  const doc = new DOMParser().parseFromString(html ?? "", "text/html");
  return (
    <>{Array.from(doc.body.childNodes).map((c, i) => convert(c, i, inline))}</>
  );
}
