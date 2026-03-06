import {
    useNotificationStore,
    type NotificationType,
} from '@/store/notificationStore';
import { toast, type ToastOptions } from 'react-toastify';

const defaultOptions: ToastOptions = {
  autoClose: 5000,
  hideProgressBar: false,
  closeOnClick: true,
  pauseOnHover: true,
  draggable: false,
};

/**
 * Show a toast AND persist the notification in the notification center (bell icon).
 * If the user clicks the toast's close button it still stays in the bell panel
 * until manually dismissed there.
 */
export function notify(
  type: NotificationType,
  message: string,
  options?: ToastOptions,
) {
  // Persist in store (bell icon)
  useNotificationStore.getState().addNotification(type, message);

  // Show ephemeral toast
  const merged: ToastOptions = { ...defaultOptions, ...options };

  switch (type) {
    case 'success':
      toast.success(message, merged);
      break;
    case 'error':
      toast.error(message, merged);
      break;
    case 'warning':
      toast.warn(message, merged);
      break;
    case 'info':
      toast.info(message, merged);
      break;
  }
}
