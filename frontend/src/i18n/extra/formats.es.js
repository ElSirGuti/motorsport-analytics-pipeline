// Formatos de telemetría (iRacing .ibt, MoTeC .ld). Los formatos nativos son EXPERIMENTALES.
export default {
  fmtExperimental: 'Experimental',
  fmtExperimentalHint: 'Formato experimental: validado con un conjunto limitado de archivos reales. Contrasta los resultados con tus datos habituales.',
  fmtDetected: 'Formato detectado: {format}',
  fmtSupportedList: '.csv (MoTeC / ACTI / export de iRacing), .ibt (iRacing, experimental), .ld (MoTeC, experimental)',
  fmtInvalidType: 'Tipo de archivo no soportado. Usa .csv, .ibt o .ld.',
  fileLabel: 'Arrastra o haz clic · .csv, .ibt o .ld · Máx {max} MB',
  shellDropHint: 'o haz clic para buscar. Archivos .csv, .ibt (iRacing) y .ld (MoTeC); .ibt y .ld son experimentales.',
  dropzoneLabel: 'Arrastra archivos de telemetría aquí',
  advValidateCsv: 'El archivo debe ser .csv, .ibt o .ld',
  advValidateSize: 'El archivo supera 500 MB',
  shellOneCsv: '1 archivo',
  shellTwoCsv: '2 archivos',
};
