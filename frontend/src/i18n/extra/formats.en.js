// Telemetry formats (iRacing .ibt, MoTeC .ld). Native formats are EXPERIMENTAL.
export default {
  fmtExperimental: 'Experimental',
  fmtExperimentalHint: 'Experimental format: validated with a limited set of real files. Check the results against your usual data.',
  fmtDetected: 'Detected format: {format}',
  fmtSupportedList: '.csv (MoTeC / ACTI / iRacing export), .ibt (iRacing, experimental), .ld (MoTeC, experimental)',
  fmtInvalidType: 'Unsupported file type. Use .csv, .ibt or .ld.',
  fileLabel: 'Drag or click · .csv, .ibt or .ld · Max {max} MB',
  shellDropHint: 'or click to browse. .csv, .ibt (iRacing) and .ld (MoTeC) files; .ibt and .ld are experimental.',
  dropzoneLabel: 'Drag telemetry files here',
  advValidateCsv: 'File must be .csv, .ibt or .ld',
  advValidateSize: 'File exceeds 500 MB',
  shellOneCsv: '1 file',
  shellTwoCsv: '2 files',
};
