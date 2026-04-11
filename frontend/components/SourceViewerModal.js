"use client";

import { useEffect } from "react";
import { X, FileText, Loader2 } from "lucide-react";

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeTerms(terms) {
  const seen = new Set();

  return (Array.isArray(terms) ? terms : [])
    .flatMap((term) => String(term || "").split(/\s+/))
    .map((term) => term.trim())
    .filter((term) => term.length > 3)
    .filter((term) => {
      const key = term.toLowerCase();
      if (seen.has(key)) {
        return false;
      }

      seen.add(key);
      return true;
    })
    .slice(0, 8);
}

function highlightText(text, terms) {
  const value = String(text || "");
  const normalizedTerms = normalizeTerms(terms);

  if (normalizedTerms.length === 0 || !value) {
    return value;
  }

  const pattern = new RegExp(`(${normalizedTerms.map(escapeRegExp).join("|")})`, "ig");
  const parts = value.split(pattern);
  const lowerTerms = new Set(normalizedTerms.map((term) => term.toLowerCase()));

  return parts.map((part, index) => {
    if (lowerTerms.has(part.toLowerCase())) {
      return (
        <mark key={`${part}-${index}`} className="rounded bg-amber-200 px-0.5 text-slate-900">
          {part}
        </mark>
      );
    }

    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

export default function SourceViewerModal({
  isOpen,
  title,
  chunks,
  loading,
  onClose,
  highlightTerms = [],
}) {
  useEffect(() => {
    const handleEscape = (event) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    if (isOpen) {
      window.addEventListener("keydown", handleEscape);
    }

    return () => window.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center px-4 py-6">
      <button
        type="button"
        className="absolute inset-0 bg-slate-950/50 backdrop-blur-sm"
        aria-label="Close source viewer"
        onClick={onClose}
      />

      <div className="relative z-10 flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.25em] text-violet-600">Source Traceability</p>
            <h3 className="mt-1 text-xl font-bold text-slate-900">{title || "Source Details"}</h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-900"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto bg-slate-50 px-6 py-6">
          {loading ? (
            <div className="flex min-h-[220px] items-center justify-center text-slate-500">
              <Loader2 className="mr-2 h-5 w-5 animate-spin" />
              Loading source chunks...
            </div>
          ) : chunks && chunks.length > 0 ? (
            <div className="space-y-4">
              {chunks.map((chunk) => (
                <div key={chunk.chunk_id} className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                  <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-3">
                    <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                      <FileText className="h-4 w-4 text-violet-600" />
                      <span>{chunk.source_file_name || "Unknown PDF"}</span>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600">
                      Page {chunk.page_number ?? "N/A"}
                    </span>
                    <span className="rounded-full bg-violet-50 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-violet-700">
                      {chunk.chunk_id}
                    </span>
                  </div>
                  <div className="px-4 py-4">
                    <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">
                      {highlightText(chunk.text, highlightTerms)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white text-sm font-medium text-slate-500">
              No source chunks found for this item.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
