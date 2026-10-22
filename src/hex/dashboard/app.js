// Lightweight navigation state for the static dashboard.
const links = document.querySelectorAll('.nav-item');
links.forEach((link) => {
  link.addEventListener('click', () => {
    links.forEach((item) => item.classList.remove('active'));
    link.classList.add('active');
  });
});
