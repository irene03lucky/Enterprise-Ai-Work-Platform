/** 真人状态：本人当前工作状态（不是考勤），AI 据此判断能否找到本人。 */
export type HumanStatus =
  | "ONLINE"
  | "IN_MEETING"
  | "CUSTOMER_VISIT"
  | "BUSINESS_TRIP"
  | "LEAVE"
  | "OFFLINE";

export const HUMAN_STATUS_LABEL: Record<HumanStatus, string> = {
  ONLINE: "在线",
  IN_MEETING: "会议中",
  CUSTOMER_VISIT: "客户拜访",
  BUSINESS_TRIP: "出差",
  LEAVE: "请假",
  OFFLINE: "离线",
};

/** 兼容历史取值 */
export const HUMAN_STATUS_VALUES: HumanStatus[] = [
  "ONLINE",
  "IN_MEETING",
  "CUSTOMER_VISIT",
  "BUSINESS_TRIP",
  "LEAVE",
  "OFFLINE",
];

export type EmployeeStatus = HumanStatus;

export const EMPLOYEE_STATUS_LABEL = HUMAN_STATUS_LABEL as Record<EmployeeStatus, string>;

/** AI 数字分身状态：关闭 / 仅辅助 / 开启代理。 */
export type AITwinStatus = "OFF" | "ASSIST" | "AGENT";

export const AI_TWIN_STATUS_LABEL: Record<AITwinStatus, string> = {
  OFF: "关闭",
  ASSIST: "仅辅助",
  AGENT: "开启代理",
};

/** AI 分身可代理的权限项。 */
export type DelegationPermissionKey =
  | "answer_project_info"
  | "report_status"
  | "receive_work_items"
  | "create_task"
  | "provide_project_docs"
  | "send_formal_reply"
  | "commit_time_or_money";

export const DELEGATION_PERMISSION_LABEL: Record<DelegationPermissionKey, string> = {
  answer_project_info: "回答项目授权信息",
  report_status: "汇报真人当前状态",
  receive_work_items: "接收工作事项",
  create_task: "创建 Task",
  provide_project_docs: "提供已有项目资料",
  send_formal_reply: "代发正式业务回复",
  commit_time_or_money: "承诺时间/金额",
};

export const DELEGATION_PERMISSION_ORDER: DelegationPermissionKey[] = [
  "answer_project_info",
  "report_status",
  "receive_work_items",
  "create_task",
  "provide_project_docs",
  "send_formal_reply",
  "commit_time_or_money",
];

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
  /** 是否为企业管理员（所有者或持有「管理员」角色） */
  is_company_admin: boolean;
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
  ai_twin_name: string | null;
  ai_twin_status: AITwinStatus;
  ai_permissions: Record<DelegationPermissionKey, boolean> | null;
  ai_twin_display_name: string | null;
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
  READY: "可检索",
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

/* ---------- Model Registry（T04.8 模型选择） ---------- */

export interface ModelInfo {
  model_id: string;
  display_name: string;
  provider: string;
  model_name: string;
  enabled: boolean;
  capabilities: string[];
  current: boolean;
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
  stage: string;
  stage_label: string | null;
  access_level: "member" | "related";
  owner_id: string | null;
  member_count: number;
  event_count: number;
  open_task_count: number;
  created_at: string;
}

/** 项目阶段流水线（接触 → 验收）。 */
export const ROOM_STAGE_ORDER: string[] = [
  "CONTACT",
  "NEGOTIATION",
  "CONTRACT_DRAFT",
  "SIGNED",
  "DELIVERY",
  "ACCEPTANCE",
];

export const ROOM_STAGE_LABEL: Record<string, string> = {
  CONTACT: "接触",
  NEGOTIATION: "洽谈",
  CONTRACT_DRAFT: "合同打磨",
  SIGNED: "签约",
  DELIVERY: "交付",
  ACCEPTANCE: "验收",
};

export interface RoomMember {
  id: string;
  room_id: string;
  employee_id: string;
  role: string;
  user_name: string | null;
  user_email: string | null;
  position: string | null;
  department_name: string | null;
  /** 项目群公开协作信息：真人状态 + AI 分身接管状态 */
  human_status?: string | null;
  ai_twin_status?: string | null;
  ai_twin_display_name?: string | null;
  created_at: string;
}

/* ---------- Room 项目聊天 ---------- */

export type RoomChatSenderKind = "USER" | "AI" | "SYSTEM";

export interface RoomChatMessage {
  id: string;
  room_id: string;
  employee_id: string | null;
  sender_kind: RoomChatSenderKind;
  /** USER=成员姓名；AI=「张三 · AI分身」；SYSTEM=null */
  sender_name: string | null;
  content: string;
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

/* ---------- Task ---------- */

export type TaskStatus = "TODO" | "IN_PROGRESS" | "DONE";

export const TASK_STATUS_LABEL: Record<TaskStatus, string> = {
  TODO: "待办",
  IN_PROGRESS: "进行中",
  DONE: "已完成",
};

export type TaskSource = "MANUAL" | "CHAT" | "WORK_EVENT" | "FOLLOW_UP" | "AI_TWIN";

export const TASK_SOURCE_LABEL: Record<TaskSource, string> = {
  MANUAL: "人工创建",
  CHAT: "AI 对话",
  WORK_EVENT: "工作事件",
  FOLLOW_UP: "后续跟进",
  AI_TWIN: "AI 分身",
};

export interface Task {
  id: string;
  company_id: string;
  room_id: string | null;
  room_name: string | null;
  title: string;
  description: string | null;
  assignee_employee_id: string | null;
  assignee_name: string | null;
  due_date: string | null;
  status: TaskStatus;
  source: TaskSource;
  source_event_id: string | null;
  source_quote: string | null;
  created_by: string | null;
  creator_name: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

/** AI 识别出的任务提案：只在用户确认后才会创建为 Task。 */
export interface TaskProposal {
  title: string;
  description: string | null;
  assignee_name: string | null;
  assignee_employee_id: string | null;
  due_date: string | null;
  source: TaskSource;
  source_event_id: string | null;
  source_quote: string | null;
}

export interface WorkEvent {
  id: string;
  room_id: string;
  employee_id: string | null;
  type: WorkEventType;
  content: string;
  visibility: "PUBLIC" | "INTERNAL";
  event_date: string;
  author_name: string | null;
  author_position: string | null;
  created_at: string;
}

/* ---------- AI 数字分身 / 工作台 ---------- */

export interface WorkbenchProfile {
  user_id: string;
  user_name: string;
  user_email: string;
  employee_id: string | null;
  company_id: string;
  company_name: string;
  department_name: string | null;
  position: string | null;
  human_status: HumanStatus;
  ai_twin_name: string | null;
  ai_twin_status: AITwinStatus;
  ai_permissions: Record<DelegationPermissionKey, boolean>;
  ai_twin_display_name: string | null;
}

export type AIActivityType = "ANSWERED" | "RECEIVED" | "TASK_CREATED" | "NEED_CONFIRM";

export const AI_ACTIVITY_TYPE_LABEL: Record<AIActivityType, string> = {
  ANSWERED: "AI 已回复",
  RECEIVED: "AI 已接收",
  TASK_CREATED: "新生成 Task",
  NEED_CONFIRM: "待本人确认",
};

export interface AIActivity {
  id: string;
  company_id: string;
  employee_id: string;
  type: AIActivityType;
  title: string;
  content: string | null;
  counterparty: string | null;
  room_id: string | null;
  room_name: string | null;
  task_id: string | null;
  resolved: boolean;
  created_at: string;
}

export interface ProjectUpdateCard {
  room_id: string;
  room_name: string;
  stage: string | null;
  stage_label: string | null;
  status: string | null;
  latest_event_id: string | null;
  latest_event_type: string | null;
  latest_event_content: string | null;
  latest_event_author: string | null;
  latest_event_at: string | null;
  open_task_count: number;
}

export interface TaskSummary {
  todo: number;
  in_progress: number;
  done: number;
  overdue: number;
}

export interface WorkbenchData {
  profile: WorkbenchProfile;
  ai_items: AIActivity[];
  today_schedules: Schedule[];
  project_updates: ProjectUpdateCard[];
  task_summary: TaskSummary;
  today: string;
}

/* ---------- Calendar / 日程 ---------- */

export type ScheduleVisibility = "PRIVATE" | "COMPANY";

export interface Schedule {
  id: string;
  company_id: string;
  user_id: string;
  title: string;
  start_time: string;
  end_time: string | null;
  room_id: string | null;
  room_name: string | null;
  note: string | null;
  visibility: ScheduleVisibility;
  created_at: string;
  updated_at: string;
}

/* ---------- 最近对话 ---------- */

export type ConversationKind = "KNOWLEDGE" | "PROJECT" | "FILE" | "GENERAL";

export const CONVERSATION_KIND_LABEL: Record<ConversationKind, string> = {
  KNOWLEDGE: "知识查询",
  PROJECT: "项目问答",
  FILE: "文件分析",
  GENERAL: "工作对话",
};

export interface Conversation {
  id: string;
  company_id: string;
  user_id: string;
  title: string;
  kind: ConversationKind;
  room_id: string | null;
  room_name: string | null;
  last_message: string | null;
  last_message_at: string;
  created_at: string;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: ConversationMessage[];
}
