import { useEffect } from 'react';

export type NotificationType = 'error' | 'success' | 'info';

interface NotificationToastProps {
  type: NotificationType;
  message: string;
  onDismiss: () => void;
}

export function NotificationToast({ type, message, onDismiss }: NotificationToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onDismiss();
    }, 5000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const styles = {
    error: {
      container: 'bg-red-50 border border-red-200',
      icon: 'text-red-500',
      text: 'text-red-800',
      close: 'text-red-400 hover:text-red-600'
    },
    success: {
      container: 'bg-green-50 border border-green-200',
      icon: 'text-green-500',
      text: 'text-green-800',
      close: 'text-green-400 hover:text-green-600'
    },
    info: {
      container: 'bg-blue-50 border border-blue-200',
      icon: 'text-blue-500',
      text: 'text-blue-800',
      close: 'text-blue-400 hover:text-blue-600'
    }
  };

  const style = styles[type];

  return (
    <div className="fixed top-4 right-4 z-50 animate-in slide-in-from-top-2 fade-in duration-300">
      <div className={`flex items-start space-x-3 p-4 rounded-lg shadow-lg backdrop-blur-sm ${style.container}`}>
        <div className="flex-shrink-0">
          <NotificationIcon type={type} className={`w-5 h-5 ${style.icon}`} />
        </div>
        <div className="flex-1">
          <p className={`text-sm font-medium ${style.text}`}>
            {message}
          </p>
        </div>
        <button
          onClick={onDismiss}
          className={`flex-shrink-0 ml-2 ${style.close}`}
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  );
}

function NotificationIcon({ type, className }: { type: NotificationType; className: string }) {
  if (type === 'error') {
    return (
      <svg className={className} fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
      </svg>
    );
  }
  
  if (type === 'success') {
    return (
      <svg className={className} fill="currentColor" viewBox="0 0 20 20">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
      </svg>
    );
  }
  
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20">
      <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
    </svg>
  );
}