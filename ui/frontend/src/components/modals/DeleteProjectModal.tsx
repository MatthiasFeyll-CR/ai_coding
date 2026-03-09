import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangleIcon, XIcon } from 'lucide-react';

interface DeleteProjectModalProps {
  open: boolean;
  projectName: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteProjectModal({
  open,
  projectName,
  onConfirm,
  onCancel,
}: DeleteProjectModalProps) {
  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
        onClick={onCancel}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 8 }}
          transition={{ duration: 0.15 }}
          onClick={(e) => e.stopPropagation()}
          className="bg-bg-secondary rounded-xl border border-border-subtle shadow-2xl w-full max-w-md mx-4"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 pt-6 pb-2">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-full bg-status-error/10">
                <AlertTriangleIcon className="w-5 h-5 text-status-error" />
              </div>
              <h2 className="text-lg font-semibold">Unlink Project</h2>
            </div>
            <button
              onClick={onCancel}
              className="p-1.5 hover:bg-bg-hover rounded-lg transition-colors text-text-muted hover:text-text-primary"
            >
              <XIcon className="w-4 h-4" />
            </button>
          </div>

          {/* Body */}
          <div className="px-6 py-4">
            <p className="text-text-secondary text-sm leading-relaxed">
              Are you sure you want to unlink{' '}
              <span className="font-semibold text-text-primary">{projectName}</span>{' '}
              from the dashboard?
            </p>
            <p className="text-text-muted text-xs mt-2">
              This will only unlink the project from the pipeline UI. Your project
              files and configuration will not be deleted.
            </p>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 pb-6 pt-2">
            <button
              onClick={onCancel}
              className="btn-secondary text-sm px-4 py-2"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              className="btn-danger text-sm px-4 py-2"
            >
              Unlink
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
