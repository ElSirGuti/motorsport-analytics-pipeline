// Tyre wear measured by the simulator (rubber grip), shown in the tyre degradation panel.
export default {
  tdGripTitle: 'Wear measured by the simulator',
  tdGripSub: 'Rubber grip left per lap: it does not depend on lap times.',
  tdGripLevel_none: 'No change',
  tdGripLevel_minimal: 'Minimal',
  tdGripLevel_moderate: 'Moderate',
  tdGripLevel_high: 'High',
  tdGripNow: 'Grip left',
  tdGripFrom: (v) => `started at ${v} %`,
  tdGripLoss: 'Grip lost',
  tdGripOverLaps: (n) => `over ${n} laps`,
  tdGripPerLap: 'Loss per lap',
  tdGripPerLapHint: 'trend of the session',
};
