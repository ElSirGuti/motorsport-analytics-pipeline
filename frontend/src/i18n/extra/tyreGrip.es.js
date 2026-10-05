// Desgaste medido por el simulador (agarre de la goma), en el panel de degradación de neumáticos.
export default {
  tdGripTitle: 'Desgaste medido por el simulador',
  tdGripSub: 'Agarre de la goma que queda por vuelta: no depende de los tiempos por vuelta.',
  tdGripLevel_none: 'Sin cambio',
  tdGripLevel_minimal: 'Mínimo',
  tdGripLevel_moderate: 'Moderado',
  tdGripLevel_high: 'Alto',
  tdGripNow: 'Agarre restante',
  tdGripFrom: (v) => `empezó en ${v} %`,
  tdGripLoss: 'Agarre perdido',
  tdGripOverLaps: (n) => `en ${n} vueltas`,
  tdGripPerLap: 'Pérdida por vuelta',
  tdGripPerLapHint: 'tendencia de la sesión',
};
