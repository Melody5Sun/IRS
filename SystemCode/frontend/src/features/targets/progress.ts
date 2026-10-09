import type { Translate } from "../../i18n/LanguageProvider";
import type { MessageKey } from "../../i18n/en";
import type { TargetJob } from "../../types/api";

// 顺序与后端 ApplicationStage 一致，即下拉框的选项顺序
const STAGE_KEYS: Record<string, MessageKey> = {
  not_applied: "targets.stage.notApplied",
  submitted: "targets.stage.submitted",
  written_test: "targets.stage.writtenTest",
  interview_1: "targets.stage.interview1",
  interview_2: "targets.stage.interview2",
  interview_3: "targets.stage.interview3",
  hr_interview: "targets.stage.hrInterview",
  manager_interview: "targets.stage.managerInterview",
  offer: "targets.stage.offer",
  rejected: "targets.stage.rejected",
};

// 已提交申请之后可选的阶段
export const APPLIED_STAGES = Object.keys(STAGE_KEYS).filter((stage) => stage !== "not_applied");

// 未知阶段原样显示，避免后端新增阶段时页面空白
export function stageLabel(stage: string, t: Translate) {
  const key = STAGE_KEYS[stage];
  return key ? t(key) : stage;
}

// 卡片和首页显示的投递进度：用户自填的说明优先
export const progressLabel = (target: TargetJob, t: Translate) => target.stage_note?.trim() || stageLabel(target.stage, t);

// 四步准备进度：JD 已匹配（加入目标即完成）、简历已改写、模拟面试已完成、已投递
export function completedSteps(target: TargetJob) {
  return 1
    + (target.rewrite_status !== "none" ? 1 : 0)
    + (target.interview_done_at ? 1 : 0)
    + (target.stage !== "not_applied" ? 1 : 0);
}

export function averageProgress(targets: TargetJob[]) {
  if (!targets.length) return 0;
  return Math.round(targets.reduce((total, target) => total + completedSteps(target) * 25, 0) / targets.length);
}
