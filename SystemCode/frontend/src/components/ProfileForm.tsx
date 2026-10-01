import { useEffect, useState, type ChangeEvent } from "react";
import { saveProfile } from "../lib/profileStorage";
import type { Profile, ProfileOptions, TargetEmploymentType, WorkMode } from "../types/profile";

const API_BASE = "http://localhost:8000/api";
const WORK_MODES: WorkMode[] = ["onsite", "hybrid", "remote"];
const EMPLOYMENT_TYPES: { value: TargetEmploymentType; label: string }[] = [
  { value: "full_time", label: "正职" },
  { value: "internship", label: "实习" },
];

interface Props {
  profile: Profile;
  onSaved: (profile: Profile) => void;
}

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

export function ProfileForm({ profile, onSaved }: Props) {
  const [options, setOptions] = useState<ProfileOptions | null>(null);
  const [targetRoles, setTargetRoles] = useState(profile.constraints.target_roles);
  const [targetIndustries, setTargetIndustries] = useState(profile.constraints.target_industries);
  const [workModes, setWorkModes] = useState(profile.constraints.work_modes);
  const [employmentTypes, setEmploymentTypes] = useState(profile.constraints.target_employment_types);
  const [notes, setNotes] = useState(profile.constraints.notes);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/profile/options`)
      .then((response) => response.json())
      .then(setOptions);
  }, []);

  // 换了一份简历后，表单里的求职约束跟着新的当前画像重置
  useEffect(() => {
    setTargetRoles(profile.constraints.target_roles);
    setTargetIndustries(profile.constraints.target_industries);
    setWorkModes(profile.constraints.work_modes);
    setEmploymentTypes(profile.constraints.target_employment_types);
    setNotes(profile.constraints.notes);
  }, [profile]);

  function handleMultiSelect(event: ChangeEvent<HTMLSelectElement>, setValue: (value: string[]) => void) {
    setValue(Array.from(event.target.selectedOptions).map((option) => option.value));
  }

  async function handleSave() {
    setMessage(null);
    setSaving(true);
    const payload: Profile = {
      resume: profile.resume,
      constraints: {
        target_roles: targetRoles,
        target_industries: targetIndustries,
        work_modes: workModes,
        target_employment_types: employmentTypes,
        notes,
      },
    };

    const response = await fetch(`${API_BASE}/profile`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setSaving(false);

    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      setMessage(`保存失败（${response.status}）：${JSON.stringify(detail?.detail ?? detail)}`);
      return;
    }

    const saved: Profile = await response.json();
    saveProfile(saved);
    onSaved(saved);
    setMessage("画像已保存到后端");
  }

  return (
    <div>
      <h2>求职约束</h2>
      <label>
        目标岗位
        <select multiple value={targetRoles} onChange={(e) => handleMultiSelect(e, setTargetRoles)}>
          {options &&
            Object.entries(options.target_role_categories).map(([category, roles]) => (
              <optgroup key={category} label={category}>
                {roles.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </optgroup>
            ))}
        </select>
      </label>
      <label>
        目标行业
        <select multiple value={targetIndustries} onChange={(e) => handleMultiSelect(e, setTargetIndustries)}>
          {options?.target_industries.map((industry) => (
            <option key={industry} value={industry}>
              {industry}
            </option>
          ))}
        </select>
      </label>
      <fieldset>
        <legend>工作模式</legend>
        {WORK_MODES.map((mode) => (
          <label key={mode}>
            <input
              type="checkbox"
              checked={workModes.includes(mode)}
              onChange={() => setWorkModes(toggle(workModes, mode))}
            />
            {mode}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>工作类型</legend>
        {EMPLOYMENT_TYPES.map(({ value, label }) => (
          <label key={value}>
            <input
              type="checkbox"
              checked={employmentTypes.includes(value)}
              onChange={() => setEmploymentTypes(toggle(employmentTypes, value))}
            />
            {label}
          </label>
        ))}
      </fieldset>
      <label>
        补充说明
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>
      <div>
        <button onClick={handleSave} disabled={saving}>
          保存画像
        </button>
      </div>
      {message && <p>{message}</p>}
    </div>
  );
}
