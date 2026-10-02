import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useLanguage } from '../context/LanguageContext';
import { Icon } from './ui';
import FormatBadge from './FormatBadge';
import { MAX_FILE_MB } from '../utils/formats';

const MAX_SIZE = MAX_FILE_MB * 1024 * 1024;

const FileUploader = ({ label, selectedFile, onFileSelect }) => {
  const { t } = useLanguage();
  const onDrop = useCallback(
    (accepted) => {
      if (accepted.length > 0) onFileSelect(accepted[0]);
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive, isDragAccept, isDragReject } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.csv'], 'application/octet-stream': ['.ibt', '.ld'] },
    maxSize: MAX_SIZE,
    multiple: false,
  });

  let stateClass = '';
  if (isDragActive && isDragAccept) stateClass = 'shell-drop--active';
  if (selectedFile)                 stateClass = 'shell-drop--accepted';
  if (isDragReject)                 stateClass = 'shell-drop--reject';

  return (
    <div
      {...getRootProps()}
      className={`shell-drop ${stateClass}`}
      aria-label={label}
      role="button"
      tabIndex={0}
    >
      <input {...getInputProps()} aria-hidden="true" />
      <Icon name={selectedFile ? 'check' : isDragActive ? 'download' : 'upload'} size={22} className="shell-drop__icon" />
      <div className="shell-drop__label">
        {selectedFile ? selectedFile.name : (isDragActive ? t.fileDropHere : label)}
      </div>
      {!selectedFile && (
        <div className="shell-drop__sub">
          {t.fileLabel.replace('{max}', MAX_SIZE / 1024 / 1024)}
        </div>
      )}
      {selectedFile && (
        <div className="shell-drop__sub">
          {(selectedFile.size / 1024).toFixed(0)} KB <FormatBadge file={selectedFile} />
        </div>
      )}
    </div>
  );
};

export default FileUploader;
