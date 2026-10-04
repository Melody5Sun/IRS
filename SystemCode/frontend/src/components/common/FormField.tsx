export function FormField({ label, value, area, onEdit }: { label: string; value: string; area?: boolean; onEdit: () => void }) {
  return (
    <label className="field">
      <span>{label}</span>
      {area ? <textarea defaultValue={value} onChange={onEdit} /> : <input defaultValue={value} onChange={onEdit} />}
    </label>
  );
}
