import { filesApi } from '@/api/client';
import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import { ChevronDownIcon, ChevronRightIcon, FileIcon, FolderIcon, FolderOpenIcon } from 'lucide-react';
import { useState } from 'react';

interface TreeNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: TreeNode[];
}

interface FileTreeProps {
  projectId: number;
  onFileSelect: (path: string) => void;
  selectedFile?: string;
}

function TreeItem({
  node,
  depth,
  projectId,
  onFileSelect,
  selectedFile,
}: {
  node: TreeNode;
  depth: number;
  projectId: number;
  onFileSelect: (path: string) => void;
  selectedFile?: string;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const [children, setChildren] = useState<TreeNode[] | null>(node.children || null);

  const isDir = node.type === 'directory';
  const isSelected = node.path === selectedFile;

  const handleClick = async () => {
    if (isDir) {
      if (!children) {
        try {
          const res = await filesApi.getTree(projectId, node.path);
          setChildren(res.data);
        } catch (err) {
          console.error('Failed to load directory:', err);
        }
      }
      setExpanded((prev) => !prev);
    } else {
      onFileSelect(node.path);
    }
  };

  return (
    <div>
      <button
        onClick={handleClick}
        className={clsx(
          'w-full flex items-center space-x-1 py-1 px-2 text-sm hover:bg-bg-hover rounded transition-colors text-left',
          isSelected && 'bg-accent-cyan/10 text-accent-cyan'
        )}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isDir ? (
          <>
            {expanded ? (
              <ChevronDownIcon className="w-3.5 h-3.5 flex-shrink-0" />
            ) : (
              <ChevronRightIcon className="w-3.5 h-3.5 flex-shrink-0" />
            )}
            {expanded ? (
              <FolderOpenIcon className="w-4 h-4 text-accent-cyan flex-shrink-0" />
            ) : (
              <FolderIcon className="w-4 h-4 text-accent-cyan flex-shrink-0" />
            )}
          </>
        ) : (
          <>
            <span className="w-3.5" />
            <FileIcon className="w-4 h-4 text-text-muted flex-shrink-0" />
          </>
        )}
        <span className="truncate">{node.name}</span>
      </button>

      {isDir && expanded && children && (
        <div>
          {children.map((child) => (
            <TreeItem
              key={child.path}
              node={child}
              depth={depth + 1}
              projectId={projectId}
              onFileSelect={onFileSelect}
              selectedFile={selectedFile}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileTree({ projectId, onFileSelect, selectedFile }: FileTreeProps) {
  const { data: rootNodes, isLoading } = useQuery({
    queryKey: ['file-tree', projectId],
    queryFn: () => filesApi.getTree(projectId).then((res) => res.data),
    enabled: !!projectId,
  });

  if (isLoading) {
    return (
      <div className="p-4 text-text-muted text-sm">Loading file tree...</div>
    );
  }

  if (!rootNodes || rootNodes.length === 0) {
    return <div className="p-4 text-text-muted text-sm">No files found</div>;
  }

  return (
    <div className="py-2 overflow-y-auto h-full">
      {rootNodes.map((node: TreeNode) => (
        <TreeItem
          key={node.path}
          node={node}
          depth={0}
          projectId={projectId}
          onFileSelect={onFileSelect}
          selectedFile={selectedFile}
        />
      ))}
    </div>
  );
}
