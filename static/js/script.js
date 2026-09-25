// College Event Management System - front-end helpers
document.addEventListener('DOMContentLoaded', function () {
  // Auto-dismiss flash messages after 5 seconds
  document.querySelectorAll('.alert-dismissible').forEach(function (alert) {
    setTimeout(function () {
      var btn = alert.querySelector('.btn-close');
      if (btn) btn.click();
    }, 5000);
  });

  // Confirm before account logout links with data-confirm
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!confirm(el.getAttribute('data-confirm'))) e.preventDefault();
    });
  });
});
