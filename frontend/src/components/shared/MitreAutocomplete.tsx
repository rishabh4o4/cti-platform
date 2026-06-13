import { useState, useRef, useEffect, useCallback } from 'react';
import { ChevronDown } from 'lucide-react';
import mitreData from '@/assets/mitre-attack.json';

interface MitreEntry {
  id: string;
  name: string;
}

interface MitreAutocompleteProps {
  type: 'tactics' | 'techniques';
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function MitreAutocomplete({ type, value, onChange, onSubmit, placeholder, className }: MitreAutocompleteProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const entries: MitreEntry[] = type === 'tactics' ? mitreData.tactics : mitreData.techniques;
  
  const filtered = value.trim()
    ? entries.filter(e => 
        e.id.toLowerCase().includes(value.toLowerCase()) ||
        e.name.toLowerCase().includes(value.toLowerCase())
      ).slice(0, 15)
    : entries.slice(0, 15);

  const handleSelect = useCallback((entry: MitreEntry) => {
    const formatted = `${entry.id}: ${entry.name}`;
    onSubmit(formatted);
    onChange('');
    setIsOpen(false);
    setFocusedIndex(-1);
  }, [onSubmit, onChange]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocusedIndex(prev => Math.min(prev + 1, filtered.length - 1));
      setIsOpen(true);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocusedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (focusedIndex >= 0 && focusedIndex < filtered.length) {
        handleSelect(filtered[focusedIndex]);
      } else if (value.trim()) {
        onSubmit(value.trim());
        onChange('');
        setIsOpen(false);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setFocusedIndex(-1);
    }
  }, [filtered, focusedIndex, handleSelect, value, onSubmit, onChange]);

  // Scroll focused item into view
  useEffect(() => {
    if (focusedIndex >= 0 && listRef.current) {
      const items = listRef.current.children;
      if (items[focusedIndex]) {
        (items[focusedIndex] as HTMLElement).scrollIntoView({ block: 'nearest' });
      }
    }
  }, [focusedIndex]);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={containerRef} className={`relative ${className || ''}`}>
      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={value}
            onChange={(e) => {
              onChange(e.target.value);
              setIsOpen(true);
              setFocusedIndex(-1);
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || `Search ${type}...`}
            className="w-full bg-background border border-border rounded px-2 py-1 text-xs focus:outline-none focus:border-primary pr-6"
            role="combobox"
            aria-expanded={isOpen}
            aria-controls={`mitre-${type}-listbox`}
            aria-autocomplete="list"
            aria-activedescendant={focusedIndex >= 0 ? `mitre-${type}-${focusedIndex}` : undefined}
          />
          <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 h-3 w-3 text-text-secondary pointer-events-none" />
        </div>
      </div>

      {isOpen && filtered.length > 0 && (
        <ul
          ref={listRef}
          id={`mitre-${type}-listbox`}
          role="listbox"
          className="absolute z-20 w-full mt-1 bg-surface border border-border rounded-md shadow-lg max-h-48 overflow-y-auto"
        >
          {filtered.map((entry, idx) => (
            <li
              key={entry.id}
              id={`mitre-${type}-${idx}`}
              role="option"
              aria-selected={focusedIndex === idx}
              className={`px-3 py-1.5 text-xs cursor-pointer flex items-center gap-2 ${
                focusedIndex === idx ? 'bg-primary/10 text-primary' : 'text-text-primary hover:bg-background'
              }`}
              onClick={() => handleSelect(entry)}
              onMouseEnter={() => setFocusedIndex(idx)}
            >
              <span className="font-mono text-[10px] text-text-secondary shrink-0 w-16">{entry.id}</span>
              <span className="truncate">{entry.name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
