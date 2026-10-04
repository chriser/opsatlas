// The document editor (CM S2–S6): WYSIWYG on top of Markdown, which stays the stored format.
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { Editor } from "@tiptap/core";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Markdown } from "@tiptap/markdown";
import { Table, TableCell, TableHeader, TableRow } from "@tiptap/extension-table";
import Image from "@tiptap/extension-image";
import { Placeholder } from "@tiptap/extensions";
import { uploadImage } from "./api";
import { tidyMarkdown } from "./markdown";
import {
  AnchorHighlights,
  applyCase,
  clearCell,
  countWords,
  duplicateRow,
  selectionAnchor,
  setAnchors,
  type Anchor,
  type CaseStyle,
} from "./extensions";

const ICONS: Record<string, string> = {
  bold: "M7 5h6a3.5 3.5 0 0 1 0 7H7zM7 12h7a3.5 3.5 0 0 1 0 7H7z",
  italic: "M11 5h6M7 19h6M14 5l-4 14",
  strike: "M5 12h14M16 6.5A4 4 0 0 0 12 5c-2.2 0-4 1.2-4 3 0 1.3.9 2.3 2.4 3M8 17.5A4 4 0 0 0 12 19c2.2 0 4-1.2 4-3",
  code: "M9 8l-4 4 4 4M15 8l4 4-4 4",
  link: "M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 0 0-5.66-5.66l-1 1M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 0 0 5.66 5.66l1-1",
  image: "M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M9 9.5h.01",
  table: "M4 5h16v14H4zM4 10h16M4 15h16M10 5v14",
  comment: "M5 5h14v10H9l-4 4z",
  bullets: "M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01",
  numbers: "M10 6h10M10 12h10M10 18h10M4 5.5h1.5V9M4 18.5h2.5L4 15.5c.7-.8 2.5-.5 2.5.8",
  indent: "M4 6h16M10 12h10M10 18h10M4 10l3 2-3 2",
  outdent: "M4 6h16M10 12h10M10 18h10M7 10l-3 2 3 2",
  quote: "M7 7h4v4c0 3-2 5-4 5M15 7h4v4c0 3-2 5-4 5",
  rule: "M4 12h16",
  undo: "M9 14L4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3",
  redo: "M15 14l5-5-5-5M20 9H10a6 6 0 0 0 0 12h3",
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
};

export function Icon({ name, size = 16 }: { name: string; size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={ICONS[name] ?? ""} />
    </svg>
  );
}

function ToolButton({
  icon,
  label,
  active,
  disabled,
  onClick,
  children,
}: {
  icon?: string;
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children?: ReactNode;
}) {
  return (
    <button
      type="button"
      className={`cm-tool${active ? " cm-tool--active" : ""}`}
      title={label}
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
    >
      {icon ? <Icon name={icon} /> : children}
    </button>
  );
}

function Menu({ label, trigger, disabled, children }: { label: string; trigger: ReactNode; disabled?: boolean; children: (close: () => void) => ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", onDown);
    return () => window.removeEventListener("mousedown", onDown);
  }, [open]);
  return (
    <div className="cm-menu" ref={ref}>
      <button
        type="button"
        className={`cm-tool cm-tool--menu${open ? " cm-tool--active" : ""}`}
        title={label}
        aria-label={label}
        aria-expanded={open}
        disabled={disabled}
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => setOpen((v) => !v)}
      >
        {trigger}
        <span className="cm-caret">▾</span>
      </button>
      {open ? <div className="cm-menu-list" role="menu">{children(() => setOpen(false))}</div> : null}
    </div>
  );
}

function MenuItem({ onClick, children, danger }: { onClick: () => void; children: ReactNode; danger?: boolean }) {
  return (
    <button type="button" role="menuitem" className={`cm-menu-item${danger ? " cm-menu-item--danger" : ""}`} onMouseDown={(e) => e.preventDefault()} onClick={onClick}>
      {children}
    </button>
  );
}

const BLOCKS: { key: string; label: string }[] = [
  { key: "p", label: "Paragraph" },
  { key: "1", label: "Heading 1" },
  { key: "2", label: "Heading 2" },
  { key: "3", label: "Heading 3" },
];

export interface EditorProps {
  markdown: string;
  editable: boolean;
  anchors: Anchor[];
  onChange: (markdown: string) => void;
  onActivateAnchor: (id: string) => void;
  onComment: (anchor: { quote: string; prefix: string; suffix: string }) => void;
  onReady: (editor: Editor | null) => void;
  onDownload: () => void;
}

export function DocumentEditor({ markdown, editable, anchors, onChange, onActivateAnchor, onComment, onReady, onDownload }: EditorProps) {
  const changeRef = useRef(onChange);
  changeRef.current = onChange;
  const activateRef = useRef(onActivateAnchor);
  activateRef.current = onActivateAnchor;
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const [imageError, setImageError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        underline: false, // Markdown cannot store it
        heading: { levels: [1, 2, 3] },
        link: { openOnClick: false, autolink: true, defaultProtocol: "https" },
      }),
      Markdown,
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
      Image.configure({ inline: false }),
      Placeholder.configure({ placeholder: "Start writing…" }),
      AnchorHighlights.configure({ onActivate: (id: string) => activateRef.current(id) }),
    ],
    content: markdown,
    contentType: "markdown",
    editable,
    shouldRerenderOnTransaction: true,
    onUpdate: ({ editor: e, transaction }) => {
      if (transaction.docChanged && !transaction.getMeta("cmExternal")) changeRef.current(tidyMarkdown(e.getMarkdown()));
    },
  });

  useEffect(() => {
    onReady(editor);
    return () => onReady(null);
  }, [editor]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    editor?.setEditable(editable);
  }, [editor, editable]);

  useEffect(() => {
    if (editor) setAnchors(editor, anchors);
  }, [editor, anchors]);

  if (!editor) return <div className="cm-canvas-loading">Opening the document…</div>;

  const { from, to, empty } = editor.state.selection;
  const selectedWords = empty ? 0 : countWords(editor.state.doc.textBetween(from, to, " ", " "));
  const totalWords = countWords(editor.state.doc.textBetween(0, editor.state.doc.content.size, " ", " "));
  const inTable = editor.isActive("table");
  const block = editor.isActive("heading", { level: 1 })
    ? "1"
    : editor.isActive("heading", { level: 2 })
      ? "2"
      : editor.isActive("heading", { level: 3 })
        ? "3"
        : "p";
  const chain = () => editor.chain().focus();

  function setBlock(key: string) {
    if (key === "p") chain().setParagraph().run();
    else chain().toggleHeading({ level: Number(key) as 1 | 2 | 3 }).run();
  }

  function openLink() {
    setLinkUrl(editor?.getAttributes("link").href ?? "");
    setLinkOpen(true);
  }

  function applyLink() {
    const url = linkUrl.trim();
    if (!url) chain().extendMarkRange("link").unsetLink().run();
    else chain().extendMarkRange("link").setLink({ href: url }).run();
    setLinkOpen(false);
  }

  async function pickImage(file: File | undefined) {
    if (!file) return;
    setImageError(null);
    try {
      const stored = await uploadImage(file);
      chain().setImage({ src: stored.url, alt: file.name.replace(/\.[^.]+$/, "") }).run();
    } catch (e) {
      setImageError(e instanceof Error ? e.message : "Could not add the image");
    }
  }

  const casing: { style: CaseStyle; label: string }[] = [
    { style: "sentence", label: "Sentence case" },
    { style: "lower", label: "lower case" },
    { style: "upper", label: "UPPER CASE" },
    { style: "title", label: "Title Case" },
  ];

  return (
    <div className="cm-editor">
      {editable ? (
        <div className="cm-toolbar" role="toolbar" aria-label="Formatting">
          <select className="cm-block-select" value={block} onChange={(e) => setBlock(e.target.value)} aria-label="Text style">
            {BLOCKS.map((b) => (
              <option key={b.key} value={b.key}>
                {b.label}
              </option>
            ))}
          </select>
          <span className="cm-sep" />
          <ToolButton icon="bold" label="Bold (⌘B)" active={editor.isActive("bold")} onClick={() => chain().toggleBold().run()} />
          <ToolButton icon="italic" label="Italic (⌘I)" active={editor.isActive("italic")} onClick={() => chain().toggleItalic().run()} />
          <ToolButton icon="strike" label="Strike-through (⌘⇧S)" active={editor.isActive("strike")} onClick={() => chain().toggleStrike().run()} />
          <ToolButton icon="code" label="Inline code" active={editor.isActive("code")} onClick={() => chain().toggleCode().run()} />
          <Menu label="Capitalisation" trigger={<span className="cm-aa">Aa</span>} disabled={empty}>
            {(close) =>
              casing.map((c) => (
                <MenuItem
                  key={c.style}
                  onClick={() => {
                    applyCase(editor, c.style);
                    close();
                  }}
                >
                  {c.label}
                </MenuItem>
              ))
            }
          </Menu>
          <span className="cm-sep" />
          <div className="cm-menu">
            <ToolButton icon="link" label="Link" active={editor.isActive("link")} onClick={openLink} />
            {linkOpen ? (
              <div className="cm-menu-list cm-link-box">
                <input
                  autoFocus
                  value={linkUrl}
                  placeholder="https://… or a page path"
                  onChange={(e) => setLinkUrl(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") applyLink();
                    if (e.key === "Escape") setLinkOpen(false);
                  }}
                />
                <button type="button" className="primary-button" onClick={applyLink}>
                  {linkUrl.trim() ? "Apply" : "Remove"}
                </button>
              </div>
            ) : null}
          </div>
          <ToolButton icon="image" label="Image" onClick={() => fileRef.current?.click()} />
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            hidden
            onChange={(e) => {
              void pickImage(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <Menu label="Table" trigger={<Icon name="table" />}>
            {(close) => (
              <>
                {!inTable ? (
                  <MenuItem
                    onClick={() => {
                      chain().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run();
                      close();
                    }}
                  >
                    Insert a table
                  </MenuItem>
                ) : (
                  <>
                    <MenuItem onClick={() => { chain().addColumnBefore().run(); close(); }}>Insert column left</MenuItem>
                    <MenuItem onClick={() => { chain().addColumnAfter().run(); close(); }}>Insert column right</MenuItem>
                    <MenuItem onClick={() => { chain().addRowBefore().run(); close(); }}>Insert row above</MenuItem>
                    <MenuItem onClick={() => { chain().addRowAfter().run(); close(); }}>Insert row below</MenuItem>
                    <MenuItem onClick={() => { duplicateRow(editor); close(); }}>Duplicate row</MenuItem>
                    <MenuItem onClick={() => { chain().toggleHeaderRow().run(); close(); }}>Header row on or off</MenuItem>
                    <MenuItem onClick={() => { if (!editor.commands.deleteSelection()) clearCell(editor); close(); }}>Clear content</MenuItem>
                    <MenuItem danger onClick={() => { chain().deleteRow().run(); close(); }}>Delete row</MenuItem>
                    <MenuItem danger onClick={() => { chain().deleteColumn().run(); close(); }}>Delete column</MenuItem>
                    <MenuItem danger onClick={() => { chain().deleteTable().run(); close(); }}>Delete table</MenuItem>
                  </>
                )}
              </>
            )}
          </Menu>
          <ToolButton
            icon="comment"
            label="Comment on the selection"
            disabled={empty}
            onClick={() => {
              const anchor = selectionAnchor(editor);
              if (anchor) onComment(anchor);
            }}
          />
          <span className="cm-sep" />
          <ToolButton icon="bullets" label="Bulleted list" active={editor.isActive("bulletList")} onClick={() => chain().toggleBulletList().run()} />
          <ToolButton icon="numbers" label="Numbered list" active={editor.isActive("orderedList")} onClick={() => chain().toggleOrderedList().run()} />
          <ToolButton icon="indent" label="Indent" disabled={!editor.can().sinkListItem("listItem")} onClick={() => chain().sinkListItem("listItem").run()} />
          <ToolButton icon="outdent" label="Outdent" disabled={!editor.can().liftListItem("listItem")} onClick={() => chain().liftListItem("listItem").run()} />
          <ToolButton icon="quote" label="Quote" active={editor.isActive("blockquote")} onClick={() => chain().toggleBlockquote().run()} />
          <ToolButton icon="rule" label="Divider" onClick={() => chain().setHorizontalRule().run()} />
          <span className="cm-sep" />
          <ToolButton icon="download" label="Download as Markdown" onClick={onDownload} />
          <ToolButton icon="undo" label="Undo (⌘Z)" disabled={!editor.can().undo()} onClick={() => chain().undo().run()} />
          <ToolButton icon="redo" label="Redo (⌘⇧Z)" disabled={!editor.can().redo()} onClick={() => chain().redo().run()} />
        </div>
      ) : (
        <div className="cm-toolbar cm-toolbar--viewing">
          <span className="muted-text">Viewing. Switch to Editing to change the document; select text to comment on it.</span>
          <span className="cm-toolbar-spacer" />
          <ToolButton
            icon="comment"
            label="Comment on the selection"
            disabled={empty}
            onClick={() => {
              const anchor = selectionAnchor(editor);
              if (anchor) onComment(anchor);
            }}
          />
          <ToolButton icon="download" label="Download as Markdown" onClick={onDownload} />
        </div>
      )}
      {imageError ? <p className="cm-inline-error">{imageError}</p> : null}
      <div className="cm-page">
        <EditorContent editor={editor} className="cm-content" />
      </div>
      <div className="cm-word-pill" aria-live="polite">
        {selectedWords ? `${selectedWords} word${selectedWords === 1 ? "" : "s"} selected` : `${totalWords} words`}
      </div>
    </div>
  );
}
