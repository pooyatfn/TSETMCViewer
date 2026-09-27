import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";

// The full content of docs/*.md and docs/adr/*.md, copied and lightly adapted
// from MkDocs syntax to plain Markdown+HTML at delivery time (admonitions →
// blockquotes, grid-cards → headings, --8<-- diagram includes → inlined SVG,
// <figure>/<figcaption> → image + caption). Nothing is summarised: this is
// the same documentation, rendered inside the panel instead of a separate site.
const rawDocs = import.meta.glob("../assets/docs-content/*.md", {
  eager: true,
  query: "?raw",
  import: "default",
}) as Record<string, string>;

const shotUrls = import.meta.glob("../assets/docs-content/screens/*.webp", {
  eager: true,
  query: "?url",
  import: "default",
}) as Record<string, string>;

function docKey(path: string): string {
  // "../assets/docs-content/06-dashboard.md" -> "06-dashboard"
  return path.split("/").pop()!.replace(/\.md$/, "");
}

const DOCS: Record<string, string> = Object.fromEntries(
  Object.entries(rawDocs).map(([path, content]) => [docKey(path), content]),
);

const SHOTS: Record<string, string> = Object.fromEntries(
  Object.entries(shotUrls).map(([path, url]) => [path.split("/").pop()!, url]),
);

interface NavItem {
  key: string;
  title: string;
}

const MAIN_NAV: NavItem[] = [
  { key: "index", title: "معرفی سرویس" },
  { key: "01-architecture", title: "معماری" },
  { key: "02-data-sources", title: "منابع داده" },
  { key: "03-data-model", title: "مدل داده" },
  { key: "04-data-quality", title: "کیفیت داده" },
  { key: "05-financial-logic", title: "منطق مالی" },
  { key: "06-dashboard", title: "پنل و نمودارها" },
  { key: "07-api", title: "API" },
  { key: "08-runbook", title: "اجرا و عملیات" },
  { key: "09-quality-engineering", title: "آزمون و مقاوم‌سازی" },
  { key: "10-limitations", title: "محدودیت‌ها" },
  { key: "11-monitoring", title: "پایش و هشدار" },
];

const ADR_NAV: NavItem[] = [
  { key: "adr__index", title: "فهرست تصمیم‌ها" },
  { key: "adr__0001-clickhouse", title: "۰۰۰۱ · ClickHouse" },
  { key: "adr__0002-python-async-stack", title: "۰۰۰۲ · Python async" },
  { key: "adr__0003-raw-first-ingestion", title: "۰۰۰۳ · داده‌ی خام اول" },
  { key: "adr__0004-scheduling", title: "۰۰۰۴ · زمان‌بندی" },
  { key: "adr__0005-migrations", title: "۰۰۰۵ · مایگریشن‌ها" },
  { key: "adr__0006-caching", title: "۰۰۰۶ · کش" },
  { key: "adr__0007-fund-identity", title: "۰۰۰۷ · شناسایی صندوق" },
  { key: "adr__0008-web-panel", title: "۰۰۰۸ · پنل وب" },
  { key: "adr__0009-observability", title: "۰۰۰۹ · قابلیت مشاهده" },
  { key: "adr__0010-high-availability", title: "۰۰۱۰ · در دسترس بودن" },
  { key: "adr__0011-clickhouse-replication", title: "۰۰۱۱ · تکثیر ClickHouse" },
  { key: "adr__0012-intraday-backfill", title: "۰۰۱۲ · بازسازی درون‌روز" },
  { key: "adr__0013-session-backfill", title: "۰۰۱۳ · بازسازی جلسه‌های قبل" },
];

/** Resolve a docs-internal .md link (however it's spelled) to one of our page keys. */
function resolveDocHref(href: string): { key: string; hash?: string } | null {
  if (/^([a-z]+:)?\/\//.test(href) || href.startsWith("mailto:")) return null; // external
  const [pathPart, hash] = href.split("#");
  if (!pathPart || !pathPart.endsWith(".md")) return null;
  const isAdr = pathPart.startsWith("adr/") || pathPart.includes("/adr/") || /(^|\/)\d{4}-/.test(pathPart);
  let base = pathPart.replace(/^\.\.\//, "").replace(/^adr\//, "");
  base = base.slice(0, -3);
  const key = isAdr ? `adr__${base}` : base;
  return DOCS[key] !== undefined ? { key, hash } : null;
}

function MarkdownImg({ src, alt }: { src?: string; alt?: string }) {
  if (!src) return null;
  const name = src.split("/").pop() ?? src;
  const url = SHOTS[name];
  if (!url) return null;
  return (
    <span className="doc-shot">
      <img src={url} alt={alt ?? ""} loading="lazy" />
    </span>
  );
}

export function Docs() {
  const [page, setPage] = useState("index");
  const [navOpen, setNavOpen] = useState(false);
  const content = DOCS[page] ?? "";

  const components = useMemo(
    () => ({
      img: MarkdownImg,
      a: ({ href, children, ...rest }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
        const resolved = href ? resolveDocHref(href) : null;
        if (resolved) {
          return (
            <a
              href={`#doc-${resolved.key}`}
              onClick={(e) => {
                e.preventDefault();
                setPage(resolved.key);
                setNavOpen(false);
                requestAnimationFrame(() => {
                  const target = (resolved.hash && document.getElementById(resolved.hash)) || document.querySelector(".doc-reader");
                  target?.scrollIntoView({ block: "start" });
                });
              }}
            >
              {children}
            </a>
          );
        }
        return (
          <a href={href} target="_blank" rel="noreferrer" {...rest}>
            {children}
          </a>
        );
      },
    }),
    [],
  );

  const go = (key: string) => {
    setPage(key);
    setNavOpen(false);
    requestAnimationFrame(() => document.querySelector(".doc-reader")?.scrollIntoView({ block: "start" }));
  };

  return (
    <div className="docs">
      <button type="button" className="doc-nav-toggle" onClick={() => setNavOpen((v) => !v)}>
        فهرست مستندات {navOpen ? "▴" : "▾"}
      </button>
      <div className={`doc-layout${navOpen ? " nav-open" : ""}`}>
        <nav className="doc-nav" aria-label="فهرست مستندات">
          <div className="doc-nav-group">
            {MAIN_NAV.map((n) => (
              <button key={n.key} type="button" className={n.key === page ? "active" : ""} onClick={() => go(n.key)}>
                {n.title}
              </button>
            ))}
          </div>
          <div className="doc-nav-heading">تصمیم‌های فنی (ADR)</div>
          <div className="doc-nav-group">
            {ADR_NAV.map((n) => (
              <button key={n.key} type="button" className={n.key === page ? "active" : ""} onClick={() => go(n.key)}>
                {n.title}
              </button>
            ))}
          </div>
        </nav>
        <article className="doc-reader">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw, rehypeSlug]}
            components={components as never}
          >
            {content}
          </ReactMarkdown>
        </article>
      </div>
    </div>
  );
}
