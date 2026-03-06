import { useAppStore } from '@/store/appStore';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangleIcon, XIcon } from 'lucide-react';

export function ErrorModal() {
  const { modals, closeModal } = useAppStore();
  const { open, error } = modals.errorDetail;

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
        onClick={() => closeModal('errorDetail')}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-bg-secondary rounded-xl border border-status-error/30 p-6 w-full max-w-lg"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2 text-status-error">
              <AlertTriangleIcon className="w-6 h-6" />
              <h2 className="text-xl font-semibold">Error Details</h2>
            </div>
            <button
              onClick={() => closeModal('errorDetail')}
              className="p-1 hover:bg-bg-hover rounded"
            >
              <XIcon className="w-5 h-5" />
            </button>
          </div>

          <div className="bg-bg-tertiary rounded-lg p-4 font-mono text-sm overflow-auto max-h-[400px]">
            {typeof error === 'string' ? (
              <p>{error}</p>
            ) : (
              <pre className="whitespace-pre-wrap">
                {JSON.stringify(error, null, 2)}
              </pre>
            )}
          </div>

          <div className="mt-4 flex justify-end">
            <button
              onClick={() => closeModal('errorDetail')}
              className="btn-secondary"
            >
              Close
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
