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

export function ReportMarkdown({ content }: { content: string }) {
  const normalized = normalizeBoldDelimiters(normalizeMarkdownTables(content ?? ""));
  return (
    <article className="animate-fade-in max-w-none text-gray-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-xl font-bold text-gray-900 mt-0 mb-4 pb-3 border-b-2 border-primary/30 tracking-tight">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-base font-bold text-gray-900 mt-6 mb-3 pb-2 border-b border-gray-200 flex items-center gap-2">
              <span className="w-1 h-5 rounded-full bg-primary shrink-0" />
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-[0.9375rem] font-semibold text-gray-800 mt-4 mb-2">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="m-0 mb-3 text-[0.9375rem] leading-[1.6] text-gray-700">
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
                    ? "my-4 pl-4 py-2.5 border-l-4 border-emerald-500/80 bg-emerald-50/60 rounded-r text-[0.9375rem] text-gray-800"
                    : "my-4 pl-4 py-2.5 border-l-4 border-amber-500/80 bg-amber-50/50 rounded-r text-[0.9375rem] text-gray-800"
                }
              >
                {children}
              </blockquote>
            );
          },
          ul: ({ children }) => (
            <ul className="list-none pl-0 my-3 space-y-2 text-[0.9375rem] text-gray-700">
              {children}
            </ul>
          ),
          li: ({ children }) => (
            <li className="flex items-start gap-2.5 leading-[1.55]">
              <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
              {children}
            </li>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-900">{children}</strong>
          ),
          table: ({ children }) => (
            <div className="my-4 overflow-x-auto rounded-lg border border-gray-200">
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
