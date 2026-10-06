// Aviso cuando el archivo cargado ya se analizó y se guardó en la biblioteca.
export default {
  libDupTitle: 'Esta sesión ya la habías analizado.',
  libDupBody: (title, when, laps) => `Está guardada en la biblioteca como "${title}"${when ? ` (${when})` : ''}${laps ? `, ${laps} vueltas` : ''}.`,
  libDupBefore: 'Ábrela para ver el resultado al instante, o analízala de nuevo.',
  libDupAfter: 'Al guardar se actualizará esa entrada en vez de crear una copia.',
  libDupOpen: 'Abrir la sesión guardada',
};
