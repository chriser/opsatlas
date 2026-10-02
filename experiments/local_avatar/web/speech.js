// Keep comparison audio understandable: only the user's chosen video plays.
const videos = [...document.querySelectorAll('video')];
for (const active of videos) {
  active.addEventListener('play', () => {
    for (const other of videos) {
      if (other !== active) other.pause();
    }
  });
}
