import type { ReactNode, ReactElement } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Fix LLM markdown: table header/separator glued with "| |" + alignment row (e.g. lunch.txt "| :-------- |") so table parses. */
function normalizeMarkdownTables(md: string): string {
  if (!md?.trim()) return md;
  return md
    .replace(/(\s*)\|\s*:([\s-]+)\s*\|/g, (_, lead, inner) => lead + "|:" + inner.replace(/\s/g, "") + "|")
    .replace(/\|\s*\|(\s*:[-|\s]+)/g, "|\n|$1")
    .replace(/([^\n])\|\s*\|(\s*:)/g, "$1|\n|$2")
    .replace(/\|[ \t]+\|(?=\s*(?::|Monday|Tuesday|Wednesday|Thursday|Friday))/g, "|\n|")
    .replace(/\|\|/g, "|\n|");
}

/** Fix bold: "**phrase: **" -> "**phrase:**" so GFM renders bold. */
function normalizeBoldDelimiters(md: string): string {
  if (!md?.trim()) return md;
  return md
    .replace(/: \*\*/g, ":**")
    .replace(/\. \*\*/g, ".**")
    .replace(/; \*\*/g, ";**")
    .replace(/! \*\*/g, "!**")
    .replace(/\? \*\*/g, "?**")
    .replace(/, \*\*/g, ",**");
}

/** Ensure newlines before block elements so LLM output that runs on one line still parses as markdown. */
function ensureBlockNewlines(md: string): string {
  if (!md?.trim()) return md;
  return md
    .replace(/\s+(####\s)/g, "\n\n#### ")
    .replace(/\s+(###\s)/g, "\n\n### ")
    .replace(/\s+(##\s)/g, "\n\n## ")
    .replace(/\s+\*\s+/g, "\n\n* ")  // bullet " * The" -> newline + "* The"
    .replace(/\s+(>\s*\*?\s*)/g, "\n\n$1");  // keep "> " or "> * "
}

export function ReportMarkdown({ content }: { content: string }) {
  const normalized = ensureBlockNewlines(
    normalizeBoldDelimiters(normalizeMarkdownTables(content ?? ""))
  );
  return (
    <article className="report-markdown animate-fade-in w-full min-w-0 max-w-none text-gray-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="report-h1 text-xl font-bold text-gray-900 mt-0 mb-5 pb-3 border-b-2 border-primary/40 tracking-tight">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="report-h2 text-[1rem] font-bold text-gray-900 mt-6 mb-2.5 pb-2 border-b border-gray-200/90 flex items-center gap-2">
              <span className="w-1 h-5 rounded-full bg-primary shrink-0" aria-hidden />
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="report-h3 text-[0.9375rem] font-semibold text-gray-800 mt-5 mb-2">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="report-h4 text-[0.9375rem] font-semibold text-primary mt-5 mb-2 pb-1.5 border-b border-primary/25">
              {children}
            </h4>
          ),
          p: ({ children }) => (
            <p className="report-p m-0 mb-3 text-[0.9375rem] leading-[1.65] text-gray-700">
              {children}
            </p>
          ),
          blockquote: ({ children }) => {
            const flatten = (node: ReactNode): string =>
              typeof node === "string"
                ? node
                : Array.isArray(node)
                  ? node.map(flatten).join(" ")
                  : (node as ReactElement)?.props?.children
                    ? flatten((node as ReactElement).props.children)
                    : "";
            const text = flatten(children);
            const isPositive = /what'?s working|working well|compliant|meets/i.test(text);
            return (
              <blockquote
                className={
                  isPositive
                    ? "report-blockquote my-4 pl-4 py-3 border-l-4 border-emerald-500/80 bg-emerald-50/60 rounded-r text-[0.9375rem] text-gray-800"
                    : "report-blockquote my-4 pl-4 py-3 border-l-4 border-primary bg-primary/5 rounded-r text-[0.9375rem] text-gray-800"
                }
              >
                {children}
              </blockquote>
            );
          },
          ul: ({ children }) => (
            <ul className="report-ul list-none pl-0 my-3 space-y-2 text-[0.9375rem] text-gray-700">
              {children}
            </ul>
          ),
          li: ({ children }) => (
            <li className="report-li flex items-start gap-2.5 leading-[1.6]">
              <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" aria-hidden />
              {children}
            </li>
          ),
          strong: ({ children }) => (
            <strong className="report-strong font-semibold text-gray-900">{children}</strong>
          ),
          table: ({ children }) => (
            <div className="report-table my-4 overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
              <table className="min-w-full text-left text-sm text-gray-700">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-gray-50 font-medium text-gray-900">{children}</thead>
          ),
          tbody: ({ children }) => <tbody className="divide-y divide-gray-200">{children}</tbody>,
          tr: ({ children }) => <tr className="border-b border-gray-100">{children}</tr>,
          th: ({ children }) => (
            <th className="px-4 py-2.5 font-semibold text-gray-800">{children}</th>
          ),
          td: ({ children }) => <td className="px-4 py-2.5">{children}</td>,
        }}
      >
        {normalized}
      </ReactMarkdown>
    </article>
  );
}
