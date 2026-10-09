import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../api";
import { profileApi } from "../../api/profile";
import { resumesApi } from "../../api/resumes";
import type { MessageKey } from "../../i18n/en";
import type {
  JobSearchConstraints, ProfileOptions, ResumeDocument, ResumeHistoryEntry,
  ResumeUpload, SavedProfile, UserProfile,
} from "../../types/api";
import { EMPTY_CONSTRAINTS, emptyProfile, NEW_ITEMS, type ListKey } from "./constants";
import type { ProfileFailure } from "./messages";
import { validateProfile } from "./validation";

type ActiveUpload = Pick<ResumeHistoryEntry, "id" | "filename" | "name" | "uploaded_at">;
type Toast = { key: MessageKey; vars?: Record<string, number> };

// 滚动到字段时让出顶部固定区域的高度
export function scrollToField(id: string) {
  const element = document.getElementById(id);
  if (element) window.scrollTo({ top: Math.max(0, element.getBoundingClientRect().top + window.scrollY - 110), behavior: "smooth" });
}

// 画像页的全部状态与接口调用：加载、上传解析、历史版本、草稿编辑、保存
export function useProfileEditor() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<UserProfile | null>(null);
  const [options, setOptions] = useState<ProfileOptions | null>(null);
  const [history, setHistory] = useState<ResumeHistoryEntry[]>([]);
  const [activeUpload, setActiveUpload] = useState<ActiveUpload | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [error, setError] = useState<ProfileFailure | null>(null);
  const [reuploadOpen, setReuploadOpen] = useState(false);
  const [overwriteTarget, setOverwriteTarget] = useState<ResumeHistoryEntry | null>(null);
  const [previewUpload, setPreviewUpload] = useState<ResumeUpload | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([profileApi.getOptions(), resumesApi.getHistory(), profileApi.get().catch((reason) => {
      if (reason instanceof ApiError && reason.status === 404) return null;
      throw reason;
    })]).then(([profileOptions, resumeHistory, saved]) => {
      if (!active) return;
      setOptions(profileOptions);
      setHistory(resumeHistory);
      if (saved) {
        setDraft({ resume: saved.resume, constraints: saved.constraints, resume_upload_id: saved.resume_upload_id });
        setUpdatedAt(saved.updated_at);
        setActiveUpload(resumeHistory.find((item) => item.id === saved.resume_upload_id) ?? null);
      } else {
        setDraft(emptyProfile());
      }
    }).catch((reason) => active && setError({ reason, action: "load" }))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, []);

  useEffect(() => () => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
  }, []);

  const showToast = (next: Toast) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(next);
    toastTimer.current = setTimeout(() => setToast(null), 2400);
  };

  const updateDraft = (recipe: (current: UserProfile) => UserProfile) => {
    setDraft((current) => current ? recipe(current) : current);
    setDirty(true);
  };

  const updateResume = <K extends keyof ResumeDocument>(key: K, value: ResumeDocument[K]) =>
    updateDraft((current) => ({ ...current, resume: { ...current.resume, [key]: value } }));

  const updateConstraint = <K extends keyof JobSearchConstraints>(key: K, value: JobSearchConstraints[K]) =>
    updateDraft((current) => ({ ...current, constraints: { ...current.constraints, [key]: value } }));

  const updateListItem = (section: ListKey, index: number, field: string, value: unknown) => {
    updateDraft((current) => {
      const list = [...current.resume[section]] as unknown as Array<Record<string, unknown>>;
      list[index] = { ...list[index], [field]: value };
      return { ...current, resume: { ...current.resume, [section]: list } as ResumeDocument };
    });
  };

  const addListItem = (section: ListKey) => {
    updateDraft((current) => ({ ...current, resume: { ...current.resume, [section]: [...current.resume[section], { ...NEW_ITEMS[section] }] } as ResumeDocument }));
  };

  const removeListItem = (section: ListKey, index: number) => {
    updateDraft((current) => ({ ...current, resume: { ...current.resume, [section]: current.resume[section].filter((_, itemIndex) => itemIndex !== index) } as ResumeDocument }));
  };

  // 用解析结果替换简历字段；求职意向保留，notes 为空时用简历里的 about 预填
  const adoptUpload = (upload: ResumeUpload) => {
    const { about, ...resume } = upload.resume;
    const constraints = draft?.constraints ?? EMPTY_CONSTRAINTS;
    setDraft({
      resume,
      constraints: { ...constraints, notes: constraints.notes || about || "" },
      resume_upload_id: upload.id,
    });
    setActiveUpload({ id: upload.id, filename: upload.filename, name: upload.name, uploaded_at: upload.uploaded_at });
    setUpdatedAt(null);
    setDirty(true);
    setAttempted(false);
    showToast({ key: "profile.toast.parsed" });
    setError(null);
  };

  const handleFile = async (file?: File) => {
    if (!file) return;
    setUploading(true); setError(null);
    try {
      const upload = await resumesApi.parsePdf(file);
      adoptUpload(upload);
      setHistory((current) => [{ id: upload.id, filename: upload.filename, name: upload.name, uploaded_at: upload.uploaded_at }, ...current.filter((item) => item.id !== upload.id)]);
    } catch (reason) {
      setError({ reason, action: "upload" });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const applyHistoryVersion = async (id: number) => {
    setUploading(true); setError(null);
    try { adoptUpload(await resumesApi.getHistoryItem(id)); }
    catch (reason) { setError({ reason, action: "load" }); }
    finally { setUploading(false); setOverwriteTarget(null); }
  };

  const previewHistory = async (id: number) => {
    setUploading(true); setError(null);
    try { setPreviewUpload(await resumesApi.getHistoryItem(id)); }
    catch (reason) { setError({ reason, action: "load" }); }
    finally { setUploading(false); }
  };

  const save = async () => {
    if (!draft) return;
    const missing = validateProfile(draft);
    if (missing.length) {
      setAttempted(true);
      showToast({ key: "profile.toast.missing", vars: { count: missing.length } });
      requestAnimationFrame(() => scrollToField(missing[0].id));
      return;
    }
    setSaving(true); setError(null);
    try {
      const saved: SavedProfile = await profileApi.save(draft);
      setDraft({ resume: saved.resume, constraints: saved.constraints, resume_upload_id: saved.resume_upload_id });
      if (!activeUpload && saved.resume_upload_id) {
        const refreshedHistory = await resumesApi.getHistory();
        setHistory(refreshedHistory);
        setActiveUpload(refreshedHistory.find((item) => item.id === saved.resume_upload_id) ?? null);
      }
      setUpdatedAt(saved.updated_at);
      setDirty(false);
      setAttempted(false);
      showToast({ key: "profile.toast.saved" });
    } catch (reason) {
      setError({ reason, action: "save" });
      // 后端 422 的 loc 形如 ["body", "resume", "educations", ...]，滚动到对应区块
      if (reason instanceof ApiError && Array.isArray(reason.body.detail)) {
        const location = reason.body.detail[0]?.loc;
        const section = location?.[1] === "resume" ? location?.[2] : location?.[1];
        document.getElementById("profile-" + String(section))?.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } finally { setSaving(false); }
  };

  // 已有上传或未保存修改时，重新上传前先弹窗确认
  const requestUpload = () => (activeUpload || dirty) ? setReuploadOpen(true) : fileRef.current?.click();
  const confirmReupload = () => { setReuploadOpen(false); fileRef.current?.click(); };

  return {
    fileRef, draft, options, history, activeUpload, updatedAt, loading, uploading, saving, dirty, attempted, toast, error,
    historyOpen, setHistoryOpen, reuploadOpen, setReuploadOpen, overwriteTarget, setOverwriteTarget, previewUpload, setPreviewUpload,
    updateResume, updateConstraint, updateListItem, addListItem, removeListItem,
    handleFile, applyHistoryVersion, previewHistory, save, requestUpload, confirmReupload,
  };
}

export type ProfileEditor = ReturnType<typeof useProfileEditor>;
