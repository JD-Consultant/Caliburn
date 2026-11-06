import { AlertCircle, LoaderCircle } from 'lucide-react';

export function LoadingState({ children = '正在讀取…' }: { children?: string }) {
  return (
    <div className="loading-state" role="status">
      <LoaderCircle aria-hidden="true" className="loading-spinner" />
      {children}
    </div>
  );
}
export function ErrorNotice({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="error-notice" role="alert">
      <AlertCircle aria-hidden="true" size={18} />
      <div>
        <p>{message}</p>
        {onRetry && (
          <button className="text-button" onClick={onRetry}>
            重新讀取
          </button>
        )}
      </div>
    </div>
  );
}
