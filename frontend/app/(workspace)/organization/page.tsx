"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/features/auth/AuthProvider";
import OrgTree, { StatusBadge, type Selection } from "@/features/organization/OrgTree";
import {
  CompanyEditModal,
  DepartmentFormModal,
  EmployeeFormModal,
  flattenDepartments,
  type DepartmentFormData,
  type EmployeeCreateFormData,
  type EmployeeEditFormData,
} from "@/features/organization/modals";
import { EditIcon, PlusIcon, TrashIcon } from "@/components/icons";
import type { CompanyTreeNode, Department, DepartmentTreeNode, Employee } from "@/lib/types";

type ModalState =
  | { kind: "company-edit" }
  | { kind: "dept-create"; lockedParent: string | null }
  | { kind: "dept-edit"; dept: Department }
  | { kind: "emp-create"; lockedDepartment: string | null }
  | { kind: "emp-edit"; employee: Employee }
  | null;

export default function OrganizationPage() {
  const router = useRouter();
  const { currentCompany, refresh } = useAuth();
  const [tree, setTree] = useState<CompanyTreeNode | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>({ type: "company" });
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [modal, setModal] = useState<ModalState>(null);

  const loadTree = useCallback(async () => {
    if (!currentCompany) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await api<{ company: CompanyTreeNode }>(
        `/companies/${currentCompany.id}/organization/tree`
      );
      setTree(resp.company);
      const ids = new Set<string>();
      const walk = (d: DepartmentTreeNode) => {
        ids.add(d.id);
        d.children.forEach(walk);
      };
      resp.company.departments.forEach(walk);
      setExpanded(ids);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载组织结构失败");
    } finally {
      setLoading(false);
    }
  }, [currentCompany]);

  useEffect(() => {
    setSelection({ type: "company" });
    loadTree();
  }, [loadTree]);

  const deptOptions = useMemo(
    () => flattenDepartments(tree?.departments ?? []),
    [tree]
  );

  const flatDepartments = useMemo(() => {
    const result: DepartmentTreeNode[] = [];
    const walk = (d: DepartmentTreeNode) => {
      result.push(d);
      d.children.forEach(walk);
    };
    (tree?.departments ?? []).forEach(walk);
    return result;
  }, [tree]);

  const allEmployees = useMemo(() => {
    const result: Employee[] = [...(tree?.unassigned_employees ?? [])];
    const walk = (d: DepartmentTreeNode) => {
      result.push(...d.employees);
      d.children.forEach(walk);
    };
    (tree?.departments ?? []).forEach(walk);
    return result;
  }, [tree]);

  if (!currentCompany) return null;
  // 闭包内使用非空常量，避免 TS 流分析的空值警告
  const companyId = currentCompany.id;
  const companyName = currentCompany.name;

  /* ---------- 详情面板 ---------- */

  function renderDetailPanel() {
    if (selection.type === "company") {
      const deptCount = flatDepartments.length;
      return (
        <div className="space-y-6">
          <div>
            <h2 className="text-base font-semibold tracking-tight">{tree?.name ?? companyName}</h2>
            <p className="mt-1 text-xs text-gray-400">企业空间</p>
          </div>
          <dl className="space-y-3 text-sm">
            <DetailRow label="行业" value={tree?.industry ?? "未设置"} />
            <DetailRow label="简介" value={tree?.description ?? "暂无简介"} />
            <DetailRow label="部门数" value={String(deptCount)} />
            <DetailRow label="员工数" value={String(allEmployees.length)} />
          </dl>
          <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-5">
            <button className="btn-secondary" onClick={() => setModal({ kind: "company-edit" })}>
              <EditIcon width={14} height={14} /> 编辑企业
            </button>
          </div>
        </div>
      );
    }

    if (selection.type === "department") {
      const dept = flatDepartments.find((d) => d.id === selection.id);
      if (!dept) return <EmptyDetail />;
      const total =
        dept.employees.length +
        dept.children.reduce((acc, c) => acc + c.employees.length, 0);
      return (
        <div className="space-y-6">
          <div>
            <h2 className="text-base font-semibold tracking-tight">{dept.name}</h2>
            <p className="mt-1 text-xs text-gray-400">部门</p>
          </div>
          <dl className="space-y-3 text-sm">
            <DetailRow label="描述" value={dept.description ?? "暂无描述"} />
            <DetailRow label="直属成员" value={String(dept.employees.length)} />
            <DetailRow label="子部门" value={String(dept.children.length)} />
            <DetailRow label="成员合计" value={String(total)} />
          </dl>
          <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-5">
            <button className="btn-secondary" onClick={() => setModal({ kind: "dept-create", lockedParent: dept.id })}>
              <PlusIcon width={14} height={14} /> 子部门
            </button>
            <button className="btn-secondary" onClick={() => setModal({ kind: "emp-create", lockedDepartment: dept.id })}>
              <PlusIcon width={14} height={14} /> 添加成员
            </button>
            <button className="btn-secondary" onClick={() => setModal({ kind: "dept-edit", dept })}>
              <EditIcon width={14} height={14} /> 编辑
            </button>
            <button
              className="btn-danger"
              onClick={async () => {
                if (!window.confirm(`确定删除部门「${dept.name}」？其子部门与成员将一并移除/移出。`)) return;
                await api(`/companies/${companyId}/departments/${dept.id}`, { method: "DELETE" });
                setSelection({ type: "company" });
                loadTree();
              }}
            >
              <TrashIcon width={14} height={14} /> 删除
            </button>
          </div>
        </div>
      );
    }

    const emp = allEmployees.find((e) => e.id === selection.id);
    if (!emp) return <EmptyDetail />;
    const dept = emp.department_id ? flatDepartments.find((d) => d.id === emp.department_id) : null;
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-900 text-base font-semibold text-white">
            {(emp.user_name ?? "?").slice(0, 1)}
          </div>
          <div>
            <h2 className="text-base font-semibold tracking-tight">{emp.user_name ?? "未命名"}</h2>
            <p className="mt-0.5 text-xs text-gray-400">{emp.user_email}</p>
          </div>
        </div>
        <dl className="space-y-3 text-sm">
          <DetailRow label="职位" value={emp.position ?? "未设置"} />
          <DetailRow label="部门" value={dept?.name ?? "未分配"} />
          <div className="flex items-center justify-between">
            <dt className="text-gray-500">工作状态</dt>
            <dd><StatusBadge status={emp.status} /></dd>
          </div>
        </dl>
        <div className="flex flex-wrap gap-2 border-t border-gray-100 pt-5">
          <button className="btn-secondary" onClick={() => setModal({ kind: "emp-edit", employee: emp })}>
            <EditIcon width={14} height={14} /> 编辑
          </button>
          <button
            className="btn-danger"
            onClick={async () => {
              if (!window.confirm(`确定将「${emp.user_name}」移出企业？`)) return;
              await api(`/companies/${companyId}/employees/${emp.id}`, { method: "DELETE" });
              setSelection({ type: "company" });
              loadTree();
            }}
          >
            <TrashIcon width={14} height={14} /> 移出企业
          </button>
        </div>
      </div>
    );
  }

  /* ---------- 弹窗动作 ---------- */

  async function submitCompanyEdit(data: { name: string; industry: string | null; description: string | null }) {
    await api(`/companies/${companyId}`, { method: "PATCH", body: data });
    setModal(null);
    await Promise.all([loadTree(), refresh()]);
  }

  async function submitDepartment(data: DepartmentFormData, mode: "create" | "edit", existingId?: string) {
    if (mode === "create") {
      await api(`/companies/${companyId}/departments`, { method: "POST", body: data });
    } else {
      await api(`/companies/${companyId}/departments/${existingId}`, {
        method: "PATCH",
        body: data,
      });
    }
    setModal(null);
    await loadTree();
  }

  async function submitEmployeeCreate(data: EmployeeCreateFormData | EmployeeEditFormData) {
    await api(`/companies/${companyId}/employees/with-user`, { method: "POST", body: data });
    setModal(null);
    await loadTree();
  }

  async function submitEmployeeEdit(data: EmployeeCreateFormData | EmployeeEditFormData, employeeId: string) {
    await api(`/companies/${companyId}/employees/${employeeId}`, {
      method: "PATCH",
      body: data,
    });
    setModal(null);
    await loadTree();
  }

  /* ---------- 渲染 ---------- */

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">组织架构</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            企业、部门与成员的组织结构。AI 将基于此理解你的企业。
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setModal({ kind: "dept-create", lockedParent: null })}>
            <PlusIcon width={14} height={14} /> 新建部门
          </button>
          <button className="btn-primary" onClick={() => setModal({ kind: "emp-create", lockedDepartment: null })}>
            <PlusIcon width={14} height={14} /> 添加员工
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-600">
          {error}
          {error.includes("401") && (
            <button className="ml-2 underline" onClick={() => router.push("/login")}>
              重新登录
            </button>
          )}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-5 gap-4">
        <div className="card col-span-3 overflow-y-auto">
          {loading && !tree ? (
            <div className="flex h-full items-center justify-center py-20 text-sm text-gray-400">
              正在加载组织结构…
            </div>
          ) : tree ? (
            <OrgTree
              tree={tree}
              expanded={expanded}
              selection={selection}
              onSelect={setSelection}
              onToggle={(id) =>
                setExpanded((prev) => {
                  const next = new Set(prev);
                  if (next.has(id)) next.delete(id);
                  else next.add(id);
                  return next;
                })
              }
            />
          ) : null}
        </div>

        <div className="card col-span-2 overflow-y-auto p-5">{renderDetailPanel()}</div>
      </div>

      {/* 弹窗 */}
      {modal?.kind === "company-edit" && tree && (
        <CompanyEditModal company={tree} onClose={() => setModal(null)} onSubmit={submitCompanyEdit} />
      )}
      {modal?.kind === "dept-create" && (
        <DepartmentFormModal
          mode="create"
          departments={deptOptions}
          lockedParent={modal.lockedParent}
          onClose={() => setModal(null)}
          onSubmit={(data) => submitDepartment(data, "create")}
        />
      )}
      {modal?.kind === "dept-edit" && (
        <DepartmentFormModal
          mode="edit"
          initial={modal.dept}
          departments={deptOptions}
          onClose={() => setModal(null)}
          onSubmit={(data) => submitDepartment(data, "edit", modal.dept.id)}
        />
      )}
      {modal?.kind === "emp-create" && (
        <EmployeeFormModal
          mode="create"
          departments={deptOptions}
          lockedDepartment={modal.lockedDepartment}
          onClose={() => setModal(null)}
          onSubmit={submitEmployeeCreate}
        />
      )}
      {modal?.kind === "emp-edit" && (
        <EmployeeFormModal
          mode="edit"
          initial={{
            name: modal.employee.user_name,
            email: modal.employee.user_email,
            department_id: modal.employee.department_id,
            position: modal.employee.position,
            status: modal.employee.status,
          }}
          departments={deptOptions}
          onClose={() => setModal(null)}
          onSubmit={(data) => submitEmployeeEdit(data, modal.employee.id)}
        />
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="shrink-0 text-gray-500">{label}</dt>
      <dd className="text-right text-gray-900">{value}</dd>
    </div>
  );
}

function EmptyDetail() {
  return (
    <div className="flex h-full items-center justify-center text-sm text-gray-400">
      选择左侧节点查看详情
    </div>
  );
}
