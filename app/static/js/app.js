// Generic confirm modal handler — all confirmations go through the Bootstrap modal.
document.addEventListener('DOMContentLoaded', function(){
  var modalEl = document.getElementById('confirmModal');
  if(!modalEl) return;
  var pendingForm = null;
  document.querySelectorAll('form[data-confirm]').forEach(function(form){
    form.addEventListener('submit', function(e){
      if(form.dataset.confirmed === '1') return;
      e.preventDefault();
      pendingForm = form;
      document.getElementById('confirmModalBody').textContent = form.getAttribute('data-confirm') || 'Yakin melanjutkan?';
      var m = new bootstrap.Modal(modalEl); m.show();
    });
  });
  document.getElementById('confirmModalBtn').addEventListener('click', function(){
    if(pendingForm){ pendingForm.dataset.confirmed='1'; pendingForm.submit(); }
  });
});
