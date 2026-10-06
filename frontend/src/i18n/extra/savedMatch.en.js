// Notice when the loaded file was already analysed and saved in the library.
export default {
  libDupTitle: 'You already analysed this session.',
  libDupBody: (title, when, laps) => `It is saved in the library as "${title}"${when ? ` (${when})` : ''}${laps ? `, ${laps} laps` : ''}.`,
  libDupBefore: 'Open it to see the result instantly, or analyse it again.',
  libDupAfter: 'Saving will update that entry instead of creating a copy.',
  libDupOpen: 'Open the saved session',
};
