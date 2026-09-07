"use client";

import {
  BuildingIcon,
  ChevronRightIcon,
  FolderIcon,
} from "@/components/icons";
import {
  EMPLOYEE_STATUS_LABEL,
  type CompanyTreeNode,
  type DepartmentTreeNode,
  type Employee,
  type EmployeeStatus,
} from "@/lib/types";

export type Selection =
  | { type: "company" }
  | { type: "department"; id: string }
  | { type: "employee"; id: string };

const STATUS_DOT: Record<EmployeeStatus, string> = {
  ACTIVE: "bg-green-500",
  LEAVE: "bg-amber-500",
  BUSINESS_TRIP: "bg-blue-500",
  OFFLINE: "bg-gray-300",
};

export function StatusBadge({ status }: { status: EmployeeStatus }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[11px] text-gray-600">
      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[status]}`} />
      {EMPLOYEE_STATUS_LABEL[status]}
    </span>
  );
}

function countAll(d: DepartmentTreeNode): number {
  return (
    d.employees.length + d.children.reduce((acc, c) => acc + countAll(c), 0)
  );
}

interface EmployeeRowProps {
  employee: Employee;
  selected: boolean;
  onSelect: () => void;
}

function EmployeeRow({ employee, selected, onSelect }: EmployeeRowProps) {
  return (
    <button
      className={`flex w-full items-center gap-2.5 rounded-lg py-1.5 pl-3 pr-2 text-left transition ${
        selected ? "bg-blue-50" : "hover:bg-gray-50"
      }`}
      onClick={onSelect}
    >
      <span
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
          selected ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-600"
        }`}
      >
        {(employee.user_name ?? "?").slice(0, 1)}
      </span>
      <span className="min-w-0 flex-1 truncate text-sm text-gray-700">
        {employee.user_name ?? "未命名"}
        {employee.position && (
          <span className="ml-1.5 text-xs text-gray-400">{employee.position}</span>
        )}
      </span>
      <span title={EMPLOYEE_STATUS_LABEL[employee.status]}>
        <span className={`block h-2 w-2 rounded-full ${STATUS_DOT[employee.status]}`} />
      </span>
    </button>
  );
}

interface DepartmentNodeProps {
  node: DepartmentTreeNode;
  expanded: Set<string>;
  selection: Selection;
  onSelect: (sel: Selection) => void;
  onToggle: (id: string) => void;
}

function DepartmentNode({ node, expanded, selection, onSelect, onToggle }: DepartmentNodeProps) {
  const isExpanded = expanded.has(node.id);
  const isSelected =
    selection.type === "department" && selection.id === node.id;
  const total = countAll(node);

  return (
    <div>
      <button
        className={`flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left transition ${
          isSelected ? "bg-blue-50" : "hover:bg-gray-50"
        }`}
        onClick={() => onSelect({ type: "department", id: node.id })}
      >
        <span
          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded text-gray-400 transition ${
            isExpanded ? "rotate-90" : ""
          }`}
          onClick={(e) => {
            e.stopPropagation();
            onToggle(node.id);
          }}
        >
          <ChevronRightIcon width={14} height={14} />
        </span>
        <FolderIcon width={15} height={15} className="shrink-0 text-gray-400" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium text-gray-700">
          {node.name}
        </span>
        {total > 0 && (
          <span className="shrink-0 rounded-full bg-gray-100 px-1.5 py-0.5 text-[11px] text-gray-500">
            {total}
          </span>
        )}
      </button>

      {isExpanded && (
        <div className="ml-4 border-l border-gray-100 pl-1.5">
          {node.employees.map((emp) => (
            <EmployeeRow
              key={emp.id}
              employee={emp}
              selected={selection.type === "employee" && selection.id === emp.id}
              onSelect={() => onSelect({ type: "employee", id: emp.id })}
            />
          ))}
          {node.children.map((child) => (
            <DepartmentNode
              key={child.id}
              node={child}
              expanded={expanded}
              selection={selection}
              onSelect={onSelect}
              onToggle={onToggle}
            />
          ))}
          {node.employees.length === 0 && node.children.length === 0 && (
            <div className="py-1.5 pl-3 text-xs text-gray-300">暂无成员</div>
          )}
        </div>
      )}
    </div>
  );
}

interface OrgTreeProps {
  tree: CompanyTreeNode;
  expanded: Set<string>;
  selection: Selection;
  onSelect: (sel: Selection) => void;
  onToggle: (id: string) => void;
}

export default function OrgTree({ tree, expanded, selection, onSelect, onToggle }: OrgTreeProps) {
  const companySelected = selection.type === "company";

  return (
    <div className="p-4">
      <button
        className={`flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left transition ${
          companySelected ? "bg-blue-50" : "hover:bg-gray-50"
        }`}
        onClick={() => onSelect({ type: "company" })}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gray-900 text-white">
          <BuildingIcon width={16} height={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-gray-900">{tree.name}</div>
          <div className="truncate text-xs text-gray-400">
            {tree.industry ?? "未设置行业"}
          </div>
        </div>
      </button>

      <div className="mt-1">
        {tree.departments.map((dept) => (
          <DepartmentNode
            key={dept.id}
            node={dept}
            expanded={expanded}
            selection={selection}
            onSelect={onSelect}
            onToggle={onToggle}
          />
        ))}
        {tree.departments.length === 0 && (
          <div className="px-3 py-2 text-xs text-gray-400">
            还没有部门，点击右上角「新建部门」开始搭建组织结构
          </div>
        )}

        {tree.unassigned_employees.length > 0 && (
          <div className="mt-2">
            <div className="px-2 py-1 text-[11px] font-medium text-gray-400">
              未分配部门
            </div>
            {tree.unassigned_employees.map((emp) => (
              <EmployeeRow
                key={emp.id}
                employee={emp}
                selected={selection.type === "employee" && selection.id === emp.id}
                onSelect={() => onSelect({ type: "employee", id: emp.id })}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
