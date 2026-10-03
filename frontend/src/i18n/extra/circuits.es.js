// Circuitos conocidos y nombres de curva.
export default {
  circuitUnknown: 'Circuito no reconocido',
  circuitUnknownHint: 'El circuito de la cabecera del archivo no está en la base de circuitos conocidos, así que las curvas conservan su número.',
  circuitMatchedHint: '{name} · {length} km · {named} curvas con nombre · confianza {confidence}',
  circuitMatchedNoCorners: '{name} · {length} km · circuito reconocido, aún sin nombres de curva · confianza {confidence}',
  circuitLowConfidence: 'baja confianza',
  circuitLowConfidenceHint: 'El circuito parece {name}, pero la vuelta medida es de {measured} m frente a {nominal} m esperados ({dev} %). Puede ser otra configuración o una vuelta incompleta, por eso se ocultan los nombres de curva.',
  circuitConfidenceHigh: 'alta',
  circuitConfidenceMedium: 'media',
  sectorStartLine: 'Salida',
  sectorFinishLine: 'Meta',
};
