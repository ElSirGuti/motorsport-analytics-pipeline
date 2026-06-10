import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

const FileUploader = ({ label, onFileSelect, selectedFile, isReference = false }) => {
  const onDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles && acceptedFiles.length > 0) {
      onFileSelect(acceptedFiles[0]);
    }
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive, isDragAccept } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
    },
    maxFiles: 1,
  });

  return (
    <div
      {...getRootProps()}
      className={`dropzone ${isDragActive ? 'dropzone--active' : ''} ${selectedFile ? 'dropzone--accepted' : ''}`}
    >
      <input {...getInputProps()} />
      <div className="dropzone__icon">
        {selectedFile ? '🏁' : isReference ? '🏎️' : '🚙'}
      </div>
      <div className="dropzone__label">
        {label}
      </div>
      {selectedFile ? (
        <div className="dropzone__filename">
          ✓ {selectedFile.name}
        </div>
      ) : (
        <div className="dropzone__sublabel">
          {isDragActive
            ? 'Suelta el archivo aquí...'
            : 'Arrastra tu CSV de ACTI o haz clic para explorar'}
        </div>
      )}
    </div>
  );
};

export default FileUploader;
