import * as monaco from 'monaco-editor';
import { useEffect, useRef } from 'react';

interface MonacoEditorProps {
  value: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (value: string) => void;
  height?: string;
}

function getLanguageFromPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase() || '';
  const langMap: Record<string, string> = {
    ts: 'typescript',
    tsx: 'typescript',
    js: 'javascript',
    jsx: 'javascript',
    py: 'python',
    json: 'json',
    md: 'markdown',
    yml: 'yaml',
    yaml: 'yaml',
    toml: 'toml',
    css: 'css',
    html: 'html',
    sh: 'shell',
    bash: 'shell',
    sql: 'sql',
    txt: 'plaintext',
  };
  return langMap[ext] || 'plaintext';
}

export function MonacoEditor({
  value,
  language = 'plaintext',
  readOnly = true,
  onChange,
  height = '100%',
}: MonacoEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Define dark theme
    monaco.editor.defineTheme('nexus-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '6b7280', fontStyle: 'italic' },
        { token: 'keyword', foreground: 'a855f7' },
        { token: 'string', foreground: '06b6d4' },
        { token: 'number', foreground: 'f59e0b' },
        { token: 'type', foreground: '22d3ee' },
      ],
      colors: {
        'editor.background': '#0a0e1a',
        'editor.foreground': '#e2e8f0',
        'editor.lineHighlightBackground': '#1a1f2e',
        'editorLineNumber.foreground': '#4b5563',
        'editorCursor.foreground': '#06b6d4',
        'editor.selectionBackground': '#06b6d430',
      },
    });

    const editor = monaco.editor.create(containerRef.current, {
      value,
      language,
      theme: 'nexus-dark',
      readOnly,
      minimap: { enabled: false },
      fontSize: 13,
      fontFamily: "'JetBrains Mono', monospace",
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      automaticLayout: true,
      padding: { top: 12 },
    });

    editorRef.current = editor;

    if (onChange) {
      editor.onDidChangeModelContent(() => {
        onChange(editor.getValue());
      });
    }

    return () => {
      editor.dispose();
    };
  }, []);

  // Update value when it changes externally
  useEffect(() => {
    const editor = editorRef.current;
    if (editor && value !== editor.getValue()) {
      editor.setValue(value);
    }
  }, [value]);

  // Update language when it changes
  useEffect(() => {
    const editor = editorRef.current;
    if (editor) {
      const model = editor.getModel();
      if (model) {
        monaco.editor.setModelLanguage(model, language);
      }
    }
  }, [language]);

  return (
    <div
      ref={containerRef}
      style={{ height, width: '100%' }}
      className="rounded-lg overflow-hidden border border-border-subtle"
    />
  );
}

export { getLanguageFromPath };
