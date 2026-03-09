interface UploadQueueProps {
  items: Array<{ filename: string; documentType: string }>;
}

export function UploadQueue({ items }: UploadQueueProps) {
  return (
    <div className="panel stack-sm">
      <div>
        <span className="eyebrow">Package composition</span>
        <h3>Expected documents</h3>
      </div>
      {items.map((item) => (
        <div key={`${item.filename}-${item.documentType}`} className="row between muted-surface">
          <span>{item.filename}</span>
          <span className="badge muted">{item.documentType}</span>
        </div>
      ))}
    </div>
  );
}
