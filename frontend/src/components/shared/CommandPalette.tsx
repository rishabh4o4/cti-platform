/* eslint-disable */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FileSearch, Globe, User, X, Command } from 'lucide-react';
import api from '@/lib/api';

// ── Public API to open the palette from anywhere ──
export const openCommandPalette = () =>
  document.dispatchEvent(new CustomEvent('open-command-palette'));

// ── Types ──
interface SearchResult {
  id: string;
  title: string;
  description?: string;
  type: 'content' | 'entity' | 'author';
  url: string;
}

const TYPE_META: Record<SearchResult['type'], { icon: typeof FileSearch; label: string }> = {
  content: { icon: FileSearch, label: 'Content' },
  entity:  { icon: Globe,      label: 'Entities' },
  author:  { icon: User,       label: 'Authors' },
};

// ── Component ──
export function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  // ── Open / close helpers ──
  const open = useCallback(() => {
    setIsOpen(true);
    setQuery('');
    setResults([]);
    setActiveIndex(0);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
    setQuery('');
    setResults([]);
    setActiveIndex(0);
  }, []);

  // ── Listen for the custom "open-command-palette" event ──
  useEffect(() => {
    const handler = () => open();
    document.addEventListener('open-command-palette', handler);
    return () => document.removeEventListener('open-command-palette', handler);
  }, [open]);

  // ── Global Cmd/Ctrl+K shortcut ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isOpen) {
          close();
        } else {
          open();
        }
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [isOpen, open, close]);

  // ── Auto-focus input when opened ──
  useEffect(() => {
    if (isOpen) {
      // Small delay so the DOM has rendered
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [isOpen]);

  // ── Debounced search ──
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (!query.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    debounceRef.current = setTimeout(async () => {
      try {
        const { data } = await api.get<{ results: Array<{ id: string; type: string; title: string; subtitle: string; url: string }>; total: number; query: string }>('/search', {
          params: { q: query, limit: 20 },
        });
        setResults(
          (data.results || []).map((r) => ({
            id: r.id,
            type: r.type as SearchResult['type'],
            title: r.title,
            description: r.subtitle,
            url: r.url,
          }))
        );
        setActiveIndex(0);
      } catch {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  // ── Flatten results to allow arrow-key navigation across groups ──
  const flatResults = results;

  // ── Group results by type ──
  const grouped = flatResults.reduce<Record<string, SearchResult[]>>((acc, r) => {
    (acc[r.type] ??= []).push(r);
    return acc;
  }, {});

  // ── Build an ordered flat list (for index mapping) ──
  const orderedResults: SearchResult[] = [];
  for (const type of ['content', 'entity', 'author'] as const) {
    if (grouped[type]) orderedResults.push(...grouped[type]);
  }

  // ── Select a result ──
  const selectResult = useCallback(
    (result: SearchResult) => {
      close();
      navigate(result.url);
    },
    [close, navigate],
  );

  // ── Keyboard navigation inside the modal ──
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        close();
        return;
      }

      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => (i + 1) % (orderedResults.length || 1));
        return;
      }

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => (i - 1 + (orderedResults.length || 1)) % (orderedResults.length || 1));
        return;
      }

      if (e.key === 'Enter' && orderedResults.length > 0) {
        e.preventDefault();
        selectResult(orderedResults[activeIndex]);
      }
    },
    [activeIndex, orderedResults, selectResult, close],
  );

  // ── Scroll active item into view ──
  useEffect(() => {
    if (!listRef.current) return;
    const active = listRef.current.querySelector('[aria-selected="true"]');
    active?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  // ── Lock body scroll while open ──
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  // Detect Mac for keyboard hint
  const isMac = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.userAgent);

  // ── Render ──
  let runningIndex = 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]"
      role="dialog"
      aria-label="Global search"
      aria-modal="true"
      onKeyDown={handleKeyDown}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/60 backdrop-blur-sm"
        onClick={close}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="relative w-full max-w-xl mx-4 rounded-xl bg-surface border border-border shadow-2xl overflow-hidden flex flex-col">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 border-b border-border">
          <Search className="h-5 w-5 text-text-secondary shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search threats, entities, authors…"
            className="flex-1 py-3.5 bg-transparent text-text-primary placeholder:text-text-secondary text-sm outline-none"
            aria-label="Search input"
          />

          {/* Keyboard hint */}
          <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-border bg-background px-1.5 py-0.5 text-[10px] font-medium text-text-secondary select-none">
            {isMac ? (
              <>
                <Command className="h-2.5 w-2.5" />
                <span>K</span>
              </>
            ) : (
              <span>Ctrl K</span>
            )}
          </kbd>

          <button
            onClick={close}
            className="p-1 rounded-md text-text-secondary hover:text-text-primary hover:bg-border transition-colors focus:outline-none focus:ring-2 focus:ring-primary"
            aria-label="Close search"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results area */}
        <ul
          ref={listRef}
          role="listbox"
          aria-label="Search results"
          className="max-h-96 overflow-y-auto overscroll-contain list-none p-0 m-0"
        >
          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center gap-2 px-4 py-8 justify-center text-text-secondary text-sm">
              <span className="inline-block h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
              Searching…
            </div>
          )}

          {/* Empty state */}
          {!isLoading && query.trim() !== '' && orderedResults.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-text-secondary">
              <Search className="h-10 w-10 mb-3 opacity-30" />
              <p className="text-sm font-medium">No results found</p>
              <p className="text-xs mt-1 opacity-70">Try a different search term</p>
            </div>
          )}

          {/* Grouped results */}
          {!isLoading &&
            (['content', 'entity', 'author'] as const).map((type) => {
              const items = grouped[type];
              if (!items || items.length === 0) return null;

              const { icon: Icon, label } = TYPE_META[type];

              return (
                <li key={type} role="presentation">
                  {/* Group header */}
                  <div className="px-4 pt-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-secondary">
                    {label}
                  </div>
                  <ul role="group" aria-label={label}>
                    {items.map((result) => {
                    const idx = runningIndex++;
                    const isActive = idx === activeIndex;

                    return (
                      <li key={result.id} role="option" aria-selected={isActive}>
                        <button
                          className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors outline-none ${
                            isActive
                              ? 'bg-primary/10 text-text-primary'
                              : 'text-text-secondary hover:bg-border/40 hover:text-text-primary'
                          }`}
                          onClick={() => selectResult(result)}
                          onMouseEnter={() => setActiveIndex(idx)}
                        >
                          <Icon className="h-4 w-4 shrink-0 opacity-60" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{result.title}</p>
                            {result.description && (
                              <p className="text-xs truncate opacity-60 mt-0.5">{result.description}</p>
                            )}
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </li>
            );
          })}

          {/* Idle state — no query yet */}
          {!isLoading && query.trim() === '' && (
            <div className="flex flex-col items-center justify-center py-12 text-text-secondary">
              <Command className="h-10 w-10 mb-3 opacity-20" />
              <p className="text-sm font-medium">Quick Search</p>
              <p className="text-xs mt-1 opacity-70">Start typing to search across the platform</p>
            </div>
          )}
        </ul>

        {/* Footer hints */}
        <div className="flex items-center gap-4 px-4 py-2 border-t border-border text-[11px] text-text-secondary select-none">
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px]">↑↓</kbd>
            navigate
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px]">↵</kbd>
            select
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-border bg-background px-1 py-0.5 font-mono text-[10px]">esc</kbd>
            close
          </span>
        </div>
      </div>
    </div>
  );
}
