"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiUpload } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { SpaceFormModal } from "@/features/knowledge/knowledgeModals";
import { BookIcon, EditIcon, PlusIcon, TrashIcon } from "@/components/icons";
import {
  DOCUMENT_STATUS_LABEL,
  SPACE_VISIBILITY_LABEL,
  type DocumentStatus,
  type KnowledgeDocument,
  type KnowledgeSpace,
  type SpaceVisibility,
} from "@/lib/types";

const STATUS_STYLE: Record<DocumentStatus, string> = {
  UPLOADED: "bg-gray-100 text-gray-600",
  PARSING: "bg-blue-50 text-blue-600",
  EMBEDDING: "bg-blue-50 text-blue-600",
  READY: "bg-green-50 text-green-600",
  FAILED: "bg-red-50 text-red-600",
};

const FILE_ICON: Record<string, string> = {
  pdf: "PDF",
  docx: "DOC",
  pptx: "PPT",
  txt: "TXT",
  md: "MD",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

type ModalState =
  | { kind: "space-create" }
  | { kind: "space-edit"; space: KnowledgeSpace }
  | null;

export default function KnowledgePage() {
  const { currentCompany } = useAuth();
  const [spaces, setSpaces] = useState<KnowledgeSpace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSpaceId, setActiveSpaceId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [uploading, setUploading] = useState(false);
  const [modal, setModal] = useState<ModalState>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadSpaces = useCallback(async () => {
    if (!currentCompany) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api<KnowledgeSpace[]>(
        `/companies/${currentCompany.id}/knowledge/spaces`
      );
      setSpaces(data);
      setActiveSpaceId((prev) =>
        prev && data.some((s) => s.id === prev) ? prev : (data[0]?.id ?? null)
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载知识空间失败");
    } finally {
      setLoading(false);
    }
  }, [currentCompany]);

  useEffect(() => {
    loadSpaces();
  }, [loadSpaces]);

  const loadDocuments = useCallback(
    async (spaceId: string) => {
      try {
        const docs = await api<KnowledgeDocument[]>(
          `/companies/${currentCompany!.id}/knowledge/spaces/${spaceId}/documents`
        );
        setDocuments(docs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "加载文档失败");
      }
    },
    [currentCompany]
  );

  // 加载当前空间文档 + 处理中文档的状态轮询
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (!activeSpaceId) {
      setDocuments([]);
      return;
    }
    loadDocuments(activeSpaceId);
    pollRef.current = setInterval(() => {
      setDocuments((docs) => {
        const pending = docs.some((d) => d.status === "UPLOADED" || d.status === "PARSING" || d.status === "EMBEDDING");
        if (pending) loadDocuments(activeSpaceId);
        return docs;
      });
    }, 2000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [activeSpaceId, loadDocuments]);

  if (!currentCompany) return null;

  const activeSpace = spaces.find((s) => s.id === activeSpaceId) ?? null;

  async function submitSpace(data: { name: string; description: string | null; visibility: SpaceVisibility }) {
    if (modal?.kind === "space-edit") {
      await api(
        `/companies/${currentCompany!.id}/knowledge/spaces/${modal.space.id}`,
        { method: "PATCH", body: data }
      );
    } else {
      const space = await api<KnowledgeSpace>(
        `/companies/${currentCompany!.id}/knowledge/spaces`,
        { method: "POST", body: data }
      );
      setActiveSpaceId(space.id);
    }
    setModal(null);
    await loadSpaces();
  }

  async function deleteSpace(space: KnowledgeSpace) {
    if (
      !window.confirm(
        `确定删除知识空间「${space.name}」？其中 ${space.document_count} 个文档及其向量数据将一并删除。`
      )
    )
      return;
    await api(`/companies/${currentCompany!.id}/knowledge/spaces/${space.id}`, {
      method: "DELETE",
    });
    setActiveSpaceId(null);
    await loadSpaces();
  }

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0 || !activeSpaceId) return;
    setUploading(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        await apiUpload<KnowledgeDocument>(
          `/companies/${currentCompany!.id}/knowledge/spaces/${activeSpaceId}/documents`,
          file
        );
      }
      await loadDocuments(activeSpaceId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function reprocessDocument(doc: KnowledgeDocument) {
    await api(
      `/companies/${currentCompany!.id}/knowledge/documents/${doc.id}/reprocess`,
      { method: "POST" }
    );
    await loadDocuments(doc.knowledge_space_id);
  }

  async function deleteDocument(doc: KnowledgeDocument) {
    if (!window.confirm(`确定删除文档「${doc.name}」？`)) return;
    await api(
      `/companies/${currentCompany!.id}/knowledge/documents/${doc.id}`,
      { method: "DELETE" }
    );
    await Promise.all([loadDocuments(doc.knowledge_space_id), loadSpaces()]);
  }

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col p-6">
      {/* 顶部 */}
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">企业知识中心</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            将企业文档转化为 AI 可检索的知识资产。
          </p>
        </div>
        <button className="btn-primary" onClick={() => setModal({ kind: "space-create" })}>
          <PlusIcon width={14} height={14} /> 新建知识空间
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-600">
          {error}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-4 gap-4">
        {/* 左：知识空间列表 */}
        <div className="card col-span-1 overflow-y-auto p-3">
          {loading ? (
            <div className="py-10 text-center text-sm text-gray-400">加载中…</div>
          ) : spaces.length === 0 ? (
            <div className="px-2 py-8 text-center text-xs leading-relaxed text-gray-400">
              还没有知识空间
              <br />
              点击右上角创建第一个
            </div>
          ) : (
            spaces.map((space) => (
              <button
                key={space.id}
                className={`mb-1 flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition ${
                  space.id === activeSpaceId
                    ? "bg-blue-50"
                    : "hover:bg-gray-50"
                }`}
                onClick={() => setActiveSpaceId(space.id)}
              >
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                    space.id === activeSpaceId ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-500"
                  }`}
                >
                  <BookIcon width={15} height={15} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-gray-900">
                    {space.name}
                  </span>
                  <span className="block text-xs text-gray-400">
                    {space.document_count} 个文档
                  </span>
                </span>
              </button>
            ))
          )}
        </div>

        {/* 右：文档资产管理 */}
        <div className="card col-span-3 flex min-h-0 flex-col">
          {!activeSpace ? (
            <div className="flex flex-1 items-center justify-center text-sm text-gray-400">
              选择左侧知识空间管理文档
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3.5">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-gray-900">
                      {activeSpace.name}
                    </span>
                    <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500">
                      {SPACE_VISIBILITY_LABEL[activeSpace.visibility]}
                    </span>
                  </div>
                  {activeSpace.description && (
                    <div className="mt-0.5 truncate text-xs text-gray-400">
                      {activeSpace.description}
                    </div>
                  )}
                </div>
                <div className="flex shrink-0 gap-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    hidden
                    accept=".pdf,.docx,.pptx,.txt,.md"
                    onChange={(e) => {
                      handleUpload(e.target.files);
                      e.target.value = "";
                    }}
                  />
                  <button
                    className="btn-secondary"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                  >
                    <PlusIcon width={14} height={14} />
                    {uploading ? "上传中…" : "上传文档"}
                  </button>
                  <button
                    className="btn-secondary"
                    onClick={() => setModal({ kind: "space-edit", space: activeSpace })}
                  >
                    <EditIcon width={14} height={14} />
                  </button>
                  <button className="btn-danger" onClick={() => deleteSpace(activeSpace)}>
                    <TrashIcon width={14} height={14} />
                  </button>
                </div>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                {documents.length === 0 ? (
                  <div className="flex h-full flex-col items-center justify-center gap-2 py-16 text-gray-400">
                    <span className="text-sm">暂无文档</span>
                    <span className="text-xs">
                      支持 PDF / DOCX / PPTX / TXT / Markdown，上传后自动解析并向量化
                    </span>
                  </div>
                ) : (
                  documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="mb-2 flex items-center gap-3 rounded-lg border border-gray-100 px-4 py-3 transition hover:border-gray-200"
                    >
                      <span className="flex h-9 w-11 shrink-0 items-center justify-center rounded-md bg-gray-100 text-[10px] font-bold tracking-tight text-gray-500">
                        {FILE_ICON[doc.file_type] ?? doc.file_type.toUpperCase()}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-gray-900">
                          {doc.name}
                        </div>
                        <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-400">
                          <span>{formatSize(doc.file_size)}</span>
                          <span>·</span>
                          <span>
                            {doc.status === "READY"
                              ? `${doc.chunk_count} 个知识块`
                              : DOCUMENT_STATUS_LABEL[doc.status]}
                          </span>
                          {doc.status === "FAILED" && doc.error_message && (
                            <span className="truncate text-red-400" title={doc.error_message}>
                              · {doc.error_message}
                            </span>
                          )}
                        </div>
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium ${
                          STATUS_STYLE[doc.status as DocumentStatus]
                        }`}
                      >
                        {DOCUMENT_STATUS_LABEL[doc.status as DocumentStatus]}
                      </span>
                      {doc.status === "FAILED" && (
                        <button
                          className="btn-secondary shrink-0 px-2.5 py-1 text-xs"
                          onClick={() => reprocessDocument(doc)}
                          title="重新处理"
                        >
                          重试
                        </button>
                      )}
                      <button
                        className="shrink-0 rounded p-1.5 text-gray-300 transition hover:bg-red-50 hover:text-red-500"
                        onClick={() => deleteDocument(doc)}
                        title="删除文档"
                      >
                        <TrashIcon width={14} height={14} />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* 弹窗 */}
      {modal?.kind === "space-create" && (
        <SpaceFormModal mode="create" onClose={() => setModal(null)} onSubmit={submitSpace} />
      )}
      {modal?.kind === "space-edit" && (
        <SpaceFormModal
          mode="edit"
          initial={modal.space}
          onClose={() => setModal(null)}
          onSubmit={submitSpace}
        />
      )}
    </div>
  );
}
