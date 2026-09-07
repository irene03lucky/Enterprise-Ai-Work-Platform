export type EmployeeStatus = "ACTIVE" | "LEAVE" | "BUSINESS_TRIP" | "OFFLINE";

export const EMPLOYEE_STATUS_LABEL: Record<EmployeeStatus, string> = {
  ACTIVE: "在岗",
  LEAVE: "休假",
  BUSINESS_TRIP: "出差",
  OFFLINE: "离线",
};

export interface User {
  id: string;
  name: string;
  email: string;
  avatar: string | null;
}

export interface CompanyBrief {
  id: string;
  name: string;
  industry: string | null;
  logo: string | null;
}

/** 用户在某个企业空间中的身份：公司 + 员工档案摘要（含部门）。 */
export interface CompanyMembership extends CompanyBrief {
  employee_id: string | null;
  department_id: string | null;
  department_name: string | null;
  position: string | null;
  status: EmployeeStatus | null;
}

export interface Company extends CompanyBrief {
  description: string | null;
  owner_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Department {
  id: string;
  company_id: string;
  parent_id: string | null;
  name: string;
  description: string | null;
  created_at: string;
}

export interface Employee {
  id: string;
  user_id: string;
  company_id: string;
  department_id: string | null;
  position: string | null;
  status: EmployeeStatus;
  created_at: string;
  updated_at: string;
  user_name: string | null;
  user_email: string | null;
  user_avatar: string | null;
}

export interface DepartmentTreeNode extends Department {
  children: DepartmentTreeNode[];
  employees: Employee[];
}

export interface CompanyTreeNode extends Company {
  departments: DepartmentTreeNode[];
  unassigned_employees: Employee[];
}

export interface MeResponse {
  user: User;
  companies: CompanyMembership[];
}

export interface Role {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  created_at: string;
}

/* ---------- Knowledge ---------- */

export type SpaceVisibility = "COMPANY" | "DEPARTMENT" | "PRIVATE";

export const SPACE_VISIBILITY_LABEL: Record<SpaceVisibility, string> = {
  COMPANY: "公开",
  DEPARTMENT: "部门",
  PRIVATE: "私有",
};

export interface KnowledgeSpace {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  visibility: SpaceVisibility;
  owner_id: string | null;
  document_count: number;
  created_at: string;
}

export type DocumentStatus =
  | "UPLOADED"
  | "PARSING"
  | "EMBEDDING"
  | "READY"
  | "FAILED";

export const DOCUMENT_STATUS_LABEL: Record<DocumentStatus, string> = {
  UPLOADED: "已上传",
  PARSING: "解析中",
  EMBEDDING: "向量化中",
  READY: "已就绪",
  FAILED: "处理失败",
};

export interface KnowledgeDocument {
  id: string;
  knowledge_space_id: string;
  company_id: string;
  name: string;
  file_type: string;
  file_size: number;
  status: DocumentStatus;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
}

/* ---------- Chat ---------- */

export interface ChatSource {
  document_id: string | null;
  name: string;
  score: number;
}

/* ---------- Project Room ---------- */

export type RoomStatus = "PLANNING" | "ACTIVE" | "PAUSED" | "COMPLETED";

export const ROOM_STATUS_LABEL: Record<RoomStatus, string> = {
  PLANNING: "筹备中",
  ACTIVE: "进行中",
  PAUSED: "已暂停",
  COMPLETED: "已完成",
};

export type WorkEventType =
  | "meeting"
  | "work_log"
  | "customer_feedback"
  | "decision"
  | "task_update"
  | "document_update";

export const WORK_EVENT_TYPE_LABEL: Record<WorkEventType, string> = {
  meeting: "会议",
  work_log: "工作日志",
  customer_feedback: "客户反馈",
  decision: "决策",
  task_update: "任务进展",
  document_update: "文档更新",
};

export interface Room {
  id: string;
  company_id: string;
  name: string;
  description: string | null;
  status: RoomStatus;
  owner_id: string | null;
  member_count: number;
  event_count: number;
  created_at: string;
}

export interface RoomMember {
  id: string;
  room_id: string;
  employee_id: string;
  role: string;
  user_name: string | null;
  user_email: string | null;
  position: string | null;
  department_name: string | null;
  created_at: string;
}

export interface RoomDocument {
  id: string;
  room_id: string;
  document_id: string;
  document_name: string | null;
  document_status: string | null;
  chunk_count: number | null;
  created_at: string;
}

export interface WorkEvent {
  id: string;
  room_id: string;
  employee_id: string | null;
  type: WorkEventType;
  content: string;
  event_date: string;
  author_name: string | null;
  author_position: string | null;
  created_at: string;
}
