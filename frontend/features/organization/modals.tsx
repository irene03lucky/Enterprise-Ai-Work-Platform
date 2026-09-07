"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import {
  EMPLOYEE_STATUS_LABEL,
  type Company,
  type Department,
  type DepartmentTreeNode,
  type EmployeeStatus,
} from "@/lib/types";

/* ---------------- 通用弹窗 ---------------- */

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative max-h-[88vh] w-[480px] max-w-[92vw] overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
        <h3 className="mb-5 text-base font-semibold tracking-tight">{title}</h3>
        {children}
      </div>
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{message}</div>
  );
}

/* 部门选项列表（扁平化树） */
export function flattenDepartments(
  nodes: DepartmentTreeNode[],
  depth = 0
): { id: string; label: string }[] {
  return nodes.flatMap((n) => [
    { id: n.id, label: `${"　".repeat(depth)}${n.name}` },
    ...flattenDepartments(n.children, depth + 1),
  ]);
}

/* ---------------- 企业编辑 ---------------- */

export function CompanyEditModal({
  company,
  onClose,
  onSubmit,
}: {
  company: Company;
  onClose: () => void;
  onSubmit: (data: { name: string; industry: string | null; description: string | null }) => Promise<void>;
}) {
  const [name, setName] = useState(company.name);
  const [industry, setIndustry] = useState(company.industry ?? "");
  const [description, setDescription] = useState(company.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        name,
        industry: industry || null,
        description: description || null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title="编辑企业信息" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="label">企业名称</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
        </div>
        <div>
          <label className="label">所在行业</label>
          <input className="input" value={industry} onChange={(e) => setIndustry(e.target.value)} maxLength={100} />
        </div>
        <div>
          <label className="label">企业简介</label>
          <textarea className="input min-h-20 resize-y" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <FormError message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn-secondary" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "保存中…" : "保存"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/* ---------------- 部门新建 / 编辑 ---------------- */

export interface DepartmentFormData {
  name: string;
  description: string | null;
  parent_id: string | null;
}

export function DepartmentFormModal({
  mode,
  initial,
  departments,
  lockedParent,
  onClose,
  onSubmit,
}: {
  mode: "create" | "edit";
  initial?: Department;
  departments: { id: string; label: string }[];
  lockedParent?: string | null;
  onClose: () => void;
  onSubmit: (data: DepartmentFormData) => Promise<void>;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [parentId, setParentId] = useState<string>(
    mode === "edit" ? (initial?.parent_id ?? "") : (lockedParent ?? "")
  );
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({
        name,
        description: description || null,
        parent_id: parentId || null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={mode === "create" ? "新建部门" : "编辑部门"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="label">部门名称</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="例如：市场部"
            required
            maxLength={200}
            autoFocus
          />
        </div>
        <div>
          <label className="label">上级部门</label>
          {mode === "create" && lockedParent !== undefined ? (
            <input className="input bg-gray-50" value={departments.find((d) => d.id === lockedParent)?.label ?? "作为一级部门"} disabled />
          ) : (
            <select className="input" value={parentId} onChange={(e) => setParentId(e.target.value)}>
              <option value="">作为一级部门</option>
              {departments
                .filter((d) => d.id !== initial?.id)
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.label}
                  </option>
                ))}
            </select>
          )}
        </div>
        <div>
          <label className="label">部门描述</label>
          <textarea
            className="input min-h-16 resize-y"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="这个部门的职责（可选）"
          />
        </div>
        <FormError message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn-secondary" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "保存中…" : mode === "create" ? "创建" : "保存"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/* ---------------- 员工新建 / 编辑 ---------------- */

export interface EmployeeCreateFormData {
  name: string;
  email: string;
  password: string;
  department_id: string | null;
  position: string | null;
  status: EmployeeStatus;
}

export interface EmployeeEditFormData {
  department_id: string | null;
  position: string | null;
  status: EmployeeStatus;
}

export function EmployeeFormModal({
  mode,
  initial,
  departments,
  lockedDepartment,
  onClose,
  onSubmit,
}: {
  mode: "create" | "edit";
  initial?: {
    name?: string | null;
    email?: string | null;
    department_id?: string | null;
    position?: string | null;
    status?: EmployeeStatus;
  };
  departments: { id: string; label: string }[];
  lockedDepartment?: string | null;
  onClose: () => void;
  onSubmit: (data: EmployeeCreateFormData | EmployeeEditFormData) => Promise<void>;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [password, setPassword] = useState("");
  const [departmentId, setDepartmentId] = useState<string>(
    mode === "edit" ? (initial?.department_id ?? "") : (lockedDepartment ?? "")
  );
  const [position, setPosition] = useState(initial?.position ?? "");
  const [status, setStatus] = useState<EmployeeStatus>(initial?.status ?? "ACTIVE");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "create") {
        await onSubmit({
          name,
          email,
          password,
          department_id: departmentId || null,
          position: position || null,
          status,
        });
      } else {
        await onSubmit({
          department_id: departmentId || null,
          position: position || null,
          status,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal title={mode === "create" ? "添加员工" : "编辑员工"} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "create" ? (
          <>
            <div>
              <label className="label">姓名</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} autoFocus />
            </div>
            <div>
              <label className="label">邮箱</label>
              <input type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="name@company.com" />
            </div>
            <div>
              <label className="label">初始密码</label>
              <input type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6} placeholder="员工首次登录密码（至少 6 位）" />
            </div>
          </>
        ) : (
          <div className="rounded-lg bg-gray-50 px-3 py-2.5 text-sm text-gray-600">
            {initial?.name} <span className="text-gray-400">· {initial?.email}</span>
          </div>
        )}

        <div>
          <label className="label">所属部门</label>
          <select className="input" value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">暂不分配部门</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">职位</label>
          <input className="input" value={position} onChange={(e) => setPosition(e.target.value)} placeholder="例如：市场总监（可选）" maxLength={100} />
        </div>
        <div>
          <label className="label">工作状态</label>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value as EmployeeStatus)}>
            {(Object.keys(EMPLOYEE_STATUS_LABEL) as EmployeeStatus[]).map((s) => (
              <option key={s} value={s}>
                {EMPLOYEE_STATUS_LABEL[s]}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-gray-400">状态用于未来 AI 理解员工工作状态，不是考勤。</p>
        </div>

        <FormError message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn-secondary" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? "保存中…" : mode === "create" ? "添加" : "保存"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
