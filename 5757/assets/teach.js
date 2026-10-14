'use strict';
document.querySelectorAll('[data-check]').forEach(button=>{
 button.addEventListener('click',()=>{
  const field=document.getElementById(button.dataset.check);
  const output=document.getElementById(button.dataset.feedback);
  if(!field.value){output.textContent='Choose an answer first, then check it.';output.hidden=false;return;}
  output.textContent=field.value===field.dataset.correct?field.dataset.right:field.dataset.wrong;
  output.hidden=false;
 });
});
