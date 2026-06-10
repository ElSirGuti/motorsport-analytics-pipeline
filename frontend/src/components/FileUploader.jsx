import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

const MAX_SIZE = 100 * 1024 * 1024; // 100 MB

const FileUploader = ({ label, selectedFile, onFileSelect }) => {
  const onDrop = useCallback(
    (accepted) => {
      if (accepted.length > 0) onFileSelect(accepted[0]);
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive, isDragAccept, isDragReject } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.csv'] },
    maxSize: MAX_SIZE,
    multiple: false,
  });

  let stateClass = '';
  if (isDragActive && isDragAccept) stateClass = 'dropzone--active';
  if (selectedFile)                 stateClass = 'dropzone--accepted';
  if (isDragReject)                 stateClass = '';

  return (
    <div
      {...getRootProps()}
      className={`dropzone ${stateClass}`}
      aria-label={label}
      role="button"
      tabIndex={0}
    >
      <input {...getInputProps()} aria-hidden="true" />
      <div className="dropzone__icon">
        {selectedFile ? '✓' : isDragActive ? '⬇' : '▤'}
      </div>
      <div className="dropzone__label">
        {selectedFile ? selectedFile.name : (isDragActive ? 'Suelta aquí' : label)}
      </div>
      {!selectedFile && (
        <div className="dropzone__sub">
          Arrastra o haz clic · Solo .csv · Máx {MAX_SIZE / 1024 / 1024} MB
        </div>
      )}
      {selectedFile && (
        <div className="dropzone__filename">
          {(selectedFile.size / 1024).toFixed(0)} KB
        </div>
      )}
    </div>
  );
};

export default FileUploader;
