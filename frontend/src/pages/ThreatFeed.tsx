/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import api from '@/lib/api';

import { Pagination } from '@/components/shared/Pagination';

import { ExternalLink, X as XIcon } from 'lucide-react';
import { ErrorState } from '@/components/shared/ErrorState';
import { Skeleton } from '@/components/shared/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';

const fetchFeed = async (page: number, entity?: string | null) => {
  const offset = (page - 1) * 10;
  const entityParam = entity ? `&entity=${encodeURIComponent(entity)}` : '';
  return (await api.get(`/content?offset=${offset}&limit=10${entityParam}`)).data;
};

export default function ThreatFeed() {
  const [page, setPage] = useState(1);
  const [searchParams, setSearchParams] = useSearchParams();
  const entityFilter = searchParams.get('entity');

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['threatFeed', page, entityFilter],
    queryFn: () => fetchFeed(page, entityFilter),
    placeholderData: keepPreviousData,
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {entityFilter && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-secondary">Filtered by entity:</span>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-medium/10 border border-medium/20 text-medium text-sm rounded-md font-mono">
            {entityFilter}
            <button
              onClick={() => { setSearchParams({}); setPage(1); }}
              className="ml-1 hover:text-critical transition-colors"
              aria-label={`Clear entity filter for ${entityFilter}`}
            >
              <XIcon className="h-3.5 w-3.5" />
            </button>
          </span>
        </div>
      )}
      <div className="bg-surface border border-border rounded-xl shadow-sm overflow-hidden flex flex-col h-[calc(100vh-16rem)] md:h-[calc(100vh-12rem)]">
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {isLoading ? (
            Array.from({length: 4}).map((_, i) => (
              <div key={i} className="bg-background border border-border rounded-lg p-4">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="flex items-center gap-3 mb-2"><Skeleton className="h-5 w-32" /></div>
                    <Skeleton className="h-6 w-64" />
                  </div>
                  <Skeleton className="h-9 w-9 rounded-md" />
                </div>
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-3/4 mb-3" />
                <Skeleton className="h-3 w-48" />
              </div>
            ))
          ) : isError ? (
            <ErrorState title="Failed to load threat feed" message="An error occurred while fetching the latest threats." onRetry={refetch} />
          ) : !data || data.items.length === 0 ? (
            <EmptyState title="No threats found" message="The threat feed is currently empty." />
          ) : (
            data.items.map((item: any) => (
                <div key={item.id} className="bg-background border border-border rounded-lg p-4 hover:border-primary/50 transition-colors">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <span className="px-2 py-0.5 bg-surface border border-border text-xs rounded text-text-secondary">
                          {item.source}
                        </span>
                      </div>
                      <h3 className="text-lg font-medium text-text-primary">{item.author_handle ? `@${item.author_handle}` : item.source_id}</h3>
                    </div>
                    <Link 
                      to={`/investigation/${item.id}`}
                      className="p-2 text-text-secondary hover:text-primary hover:bg-primary/10 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
                      aria-label={`Investigate ${item.id}`}
                    >
                      <ExternalLink className="h-5 w-5" />
                    </Link>
                  </div>
                  <p className="text-sm text-text-secondary line-clamp-2 mb-3">
                    {item.raw_text}
                  </p>
                  <div className="text-xs text-text-secondary flex items-center">
                    <span>{new Date(item.collected_at).toLocaleString()}</span>
                  </div>
              </div>
            ))
          )}
        </div>
        {data && (
          <div className="border-t border-border bg-surface">
            <Pagination 
              currentPage={page}
              totalPages={Math.ceil(data.total / data.limit) || 1}
              onPageChange={setPage}
            />
          </div>
        )}
      </div>
    </div>
  );
}
