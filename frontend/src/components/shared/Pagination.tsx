import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export function Pagination({ currentPage, totalPages, onPageChange, className }: PaginationProps) {
  return (
    <div className={cn("flex items-center justify-between px-4 py-3 sm:px-6", className)} aria-label="Pagination">
      <div className="flex flex-1 justify-between sm:hidden">
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="relative inline-flex items-center rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary hover:bg-border disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          Previous
        </button>
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="relative ml-3 inline-flex items-center rounded-md border border-border bg-surface px-4 py-2 text-sm font-medium text-text-primary hover:bg-border disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-primary"
        >
          Next
        </button>
      </div>
      <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-text-secondary">
            Page <span className="font-medium text-text-primary">{currentPage}</span> of <span className="font-medium text-text-primary">{totalPages}</span>
          </p>
        </div>
        <div>
          <nav className="isolate inline-flex -space-x-px rounded-md shadow-sm" aria-label="Pagination Navigation">
            <button
              onClick={() => onPageChange(currentPage - 1)}
              disabled={currentPage === 1}
              className="relative inline-flex items-center rounded-l-md px-2 py-2 text-text-secondary ring-1 ring-inset ring-border hover:bg-border disabled:opacity-50 focus:z-20 focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-5 w-5" aria-hidden="true" />
            </button>
            <button
              onClick={() => onPageChange(currentPage + 1)}
              disabled={currentPage === totalPages}
              className="relative inline-flex items-center rounded-r-md px-2 py-2 text-text-secondary ring-1 ring-inset ring-border hover:bg-border disabled:opacity-50 focus:z-20 focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Next page"
            >
              <ChevronRight className="h-5 w-5" aria-hidden="true" />
            </button>
          </nav>
        </div>
      </div>
    </div>
  );
}
