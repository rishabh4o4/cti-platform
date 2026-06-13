/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useRef, useCallback, useReducer, useState } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import api from '@/lib/api';
import { type RiskLabel } from '@/types';

export type Alert = {
  id: string;
  severity: RiskLabel;
  title: string;
  source: string;
  timestamp: string;
  [key: string]: any;
};

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

type AlertAction =
  | { type: 'ADD_BURST'; payload: Alert[] }
  | { type: 'ADD_SINGLE'; payload: Alert }
  | { type: 'ADD_MULTIPLE'; payload: Alert[] }
  | { type: 'CLEAR' };

function alertReducer(state: Alert[], action: AlertAction): Alert[] {
  switch (action.type) {
    case 'ADD_BURST': {
      const burstAlerts = action.payload.map(a => ({ ...a, isBurst: true }));
      return [...burstAlerts, ...state].slice(0, 100);
    }
    case 'ADD_SINGLE':
      return [action.payload, ...state].slice(0, 100);
    case 'ADD_MULTIPLE':
      return [...action.payload, ...state].slice(0, 100);
    case 'CLEAR':
      return [];
    default:
      return state;
  }
}

export function useAlertWebSocket() {
  const [alerts, dispatch] = useReducer(alertReducer, []);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  
  const token = useAuthStore((state) => state.token);
  const maxReconnectAttempts = 5;

  useEffect(() => {
    const connect = () => {
      if (!token) return;
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      setConnectionStatus('connecting');
      let wsUrl = import.meta.env.VITE_WS_BASE_URL;
      if (!wsUrl) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${protocol}//${window.location.host}/api/v1/alerts/ws`;
      }
      const ws = new WebSocket(`${wsUrl}`);

      ws.onopen = () => {
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
        ws.send(JSON.stringify({ type: 'auth', token }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'alert_burst') {
            dispatch({ type: 'ADD_BURST', payload: data.alerts });
          } else if (data.type === 'alert') {
            dispatch({ type: 'ADD_SINGLE', payload: data.alert });
          } else {
            if (Array.isArray(data)) {
              dispatch({ type: 'ADD_MULTIPLE', payload: data });
            } else {
              dispatch({ type: 'ADD_SINGLE', payload: data });
            }
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message', err);
        }
      };

      ws.onclose = async (event) => {
        setConnectionStatus('disconnected');
        
        if (event.code === 4001) {
          try {
            await api.get('/users/me'); // triggers silent refresh
          } catch {
            return; // logout will handle redirection
          }
          return;
        }

        if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error('Max WebSocket reconnect attempts reached');
          setConnectionStatus('error');
          return;
        }

        const backoff = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
        reconnectAttemptsRef.current += 1;
        
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, backoff);
      };

      ws.onerror = () => {
        setConnectionStatus('error');
      };

      wsRef.current = ws;
    };

    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [token]);

  const clearAlerts = useCallback(() => {
    dispatch({ type: 'CLEAR' });
  }, []);

  const reconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
  }, []);

  return { alerts, connectionStatus, clearAlerts, reconnect };
}
