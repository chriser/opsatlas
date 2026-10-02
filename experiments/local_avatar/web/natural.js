import '/speech.js';

const labels = {neural: 'Neural speech model', ridge: 'Linear speech model',
  amplitude_rule: 'Amplitude rule', mean: 'Fixed mean mouth', closed: 'Closed-mouth baseline'};
try {
  const response = await fetch('/natural-summary.json');
  if (!response.ok) throw new Error('Local result unavailable');
  const result = await response.json();
  if (result.schema_version !== 1 || result.session !== 'B' || result.test_evaluated !== false) {
    throw new Error('Unexpected experiment summary');
  }
  const chosen = result.validation[result.selected_predictor];
  document.querySelector('#selected-model').textContent = `${labels[result.selected_predictor]} · selected on B`;
  document.querySelector('#model-stats').textContent = `${result.parameters.toLocaleString()} parameters; best epoch ${result.selected_epoch}. A supplied ${result.training_frames.toLocaleString()} labelled timestamps; B supplied ${result.validation_frames.toLocaleString()} validation timestamps.`;
  document.querySelector('#error-stats').textContent = `Selected mouth error: ${chosen.centered_landmark_rmse_pixels.toFixed(2)} pixels in a 256-pixel face crop. Opening-ratio error: ${chosen.aperture_mae_ratio.toFixed(3)}; width error: ${chosen.width_mae_pixels.toFixed(2)} pixels.`;
  const linear = result.validation.ridge;
  const difference = 100 * (1 - chosen.selection_score / linear.selection_score);
  document.querySelector('#baseline-stats').textContent = `Combined shape score is ${Math.abs(difference).toFixed(1)}% ${difference >= 0 ? 'lower' : 'higher'} than the linear baseline. This score includes opening and width, with scales fitted on A.`;
} catch {
  document.querySelector('#selected-model').textContent = 'Result unavailable';
  document.querySelector('#model-stats').textContent = 'The local experiment summary is not ready.';
}
