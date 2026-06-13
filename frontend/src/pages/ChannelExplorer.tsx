/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useEffect, useMemo } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import api from '@/lib/api';
import { Pagination } from '@/components/shared/Pagination';
import { ExternalLink, Search } from 'lucide-react';
import { ErrorState } from '@/components/shared/ErrorState';
import { Skeleton } from '@/components/shared/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';

const fetchChannels = async (page: number, query: string) => {
  const offset = (page - 1) * 10;
  const q = query ? `&q=${encodeURIComponent(query)}` : '';
  return (await api.get(`/content?source=telegram&offset=${offset}&limit=10${q}`)).data;
};

export default function ChannelExplorer() {
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['channelExplorer', page, debouncedQuery],
    queryFn: () => fetchChannels(page, debouncedQuery),
    placeholderData: keepPreviousData,
  });

  const filteredItems = useMemo(() => {
    const items = data?.items;
    if (!items) return [];
    if (!debouncedQuery) return items;
    const lowerQuery = debouncedQuery.toLowerCase();
    return items.filter((item: any) => 
      (item.author_handle && item.author_handle.toLowerCase().includes(lowerQuery)) ||
      (item.raw_text && item.raw_text.toLowerCase().includes(lowerQuery)) ||
      (item.source_id && item.source_id.toLowerCase().includes(lowerQuery))
    );
  }, [data, debouncedQuery]);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-end gap-4">
        <div className="relative w-full sm:w-96">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-text-secondary" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2 border border-border rounded-md bg-surface text-text-primary placeholder-text-secondary focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background sm:text-sm transition-colors"
            placeholder="Search channels..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />
        </div>
      </div>
      
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
            <ErrorState title="Failed to load channels" message="An error occurred while fetching the channel list." onRetry={refetch} />
          ) : !data || filteredItems.length === 0 ? (
            <EmptyState title="No channels found" message="No channels match your current search query." />
          ) : (
            filteredItems.map((item: any) => (
                <div key={item.id} className="bg-background border border-border rounded-lg p-4 hover:border-primary/50 transition-colors">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <div className="flex items-center gap-3 mb-1">
                        <span className="px-2 py-0.5 bg-primary/10 border border-primary/20 text-xs rounded text-primary font-medium">
                          {item.source}
                        </span>
                      </div>
                      <h3 className="text-lg font-medium text-text-primary">{item.author_handle ? `@${item.author_handle}` : item.source_id}</h3>
                    </div>
                    <Link 
                      to={`/investigation/${item.id}`}
                      className="p-2 text-text-secondary hover:text-primary hover:bg-primary/10 rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background"
                      aria-label={`Investigate channel ${item.id}`}
                    >
                      <ExternalLink className="h-5 w-5" />
                    </Link>
                  </div>
                  <p className="text-sm text-text-secondary line-clamp-2 mb-3">
                    {item.raw_text}
                  </p>
                  <div className="text-xs text-text-secondary">
                    Last active: {new Date(item.collected_at).toLocaleString()}
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
