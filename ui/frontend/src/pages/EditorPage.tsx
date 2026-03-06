import { filesApi } from '@/api/client';
import { FileTree } from '@/components/editor/FileTree';
import { MonacoEditor, getLanguageFromPath } from '@/components/editor/MonacoEditor';
import { EmptyState } from '@/components/shared/EmptyState';
import { useAppStore } from '@/store/appStore';
import { useQuery } from '@tanstack/react-query';
import { FileIcon, FolderOpenIcon } from 'lucide-react';
import { useState } from 'react';

export function EditorPage() {
  const { activeProject } = useAppStore();
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const { data: fileContent, isLoading } = useQuery({
    queryKey: ['file-content', activeProject?.id, selectedFile],
    queryFn: () =>
      filesApi.readFile(activeProject!.id, selectedFile!).then((res) => res.data),
    enabled: !!activeProject?.id && !!selectedFile,
  });

  if (!activeProject) {
    return (
      <EmptyState
        icon={FolderOpenIcon}
        title="No Project Selected"
        description="Select a project from the sidebar to browse its files."
      />
    );
  }

  return (
    <div className="flex h-[calc(100vh-8rem)]">
      {/* File tree sidebar */}
      <div className="w-64 flex-shrink-0 border-r border-border-subtle bg-bg-secondary overflow-hidden">
        <div className="p-3 border-b border-border-subtle">
          <h3 className="text-sm font-medium text-text-secondary">Explorer</h3>
        </div>
        <FileTree
          projectId={activeProject.id}
          onFileSelect={setSelectedFile}
          selectedFile={selectedFile || undefined}
        />
      </div>

      {/* Editor area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedFile ? (
          <>
            <div className="flex items-center space-x-2 px-4 py-2 border-b border-border-subtle bg-bg-secondary">
              <FileIcon className="w-4 h-4 text-text-muted" />
              <span className="text-sm font-mono text-text-secondary">
                {selectedFile}
              </span>
            </div>
            <div className="flex-1">
              {isLoading ? (
                <div className="flex items-center justify-center h-full text-text-muted">
                  Loading file...
                </div>
              ) : (
                <MonacoEditor
                  value={fileContent?.content || ''}
                  language={getLanguageFromPath(selectedFile)}
                  readOnly
                />
              )}
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full">
            <EmptyState
              icon={FileIcon}
              title="No File Selected"
              description="Select a file from the tree to view its contents."
            />
          </div>
        )}
      </div>
    </div>
  );
}
