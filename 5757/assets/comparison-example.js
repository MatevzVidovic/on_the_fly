'use strict';
// All scenario amounts are invented lesson data, expressed in cents.
document.querySelectorAll('[data-comparison-example]').forEach(root=>{
 const scenarios={
  calculated:{isam:10000025,ev:10000000,genIsam:10000000,genEv:10000000,status:'RAZLIKA',genStatus:'ENAKO',outcome:'Create intermediate comparison: both calculated values are valid, and |0.25| > 0.10. Identical generalized values do not erase this difference.'},
  generalized:{isam:10000000,ev:10000000,genIsam:10000000,genEv:10100000,status:'ENAKO',genStatus:'RAZLIKA',outcome:'Save the generalized-only difference, but skip intermediate comparison by default. The calculated delta is zero. Investigate rounding policy separately.'},
  missing:{isam:10000025,ev:null,genIsam:10000000,genEv:null,status:'MANJKA_EV',genStatus:'MANJKA_EV',outcome:'Keep this final row, with EV missing. Deltas cannot be calculated. No intermediate comparison can be performed against an absent counterpart.'},
  error:{isam:10000025,ev:null,genIsam:10000000,genEv:null,status:'NAPAKA_EV',genStatus:'NAPAKA_EV',outcome:'Keep the EV calculation failure and its diagnostic. This scenario has neither usable EV value. Do not replace either with zero or create a normal detail comparison.'}
 };
 const choice=root.querySelector('select');
 const format=cents=>cents===null?'—':(cents/100).toFixed(2);
 const set=(name,value)=>{root.querySelector('[data-value="'+name+'"]').textContent=value;};
 function render(){const s=scenarios[choice.value];set('isam',format(s.isam));set('ev',format(s.ev));set('delta',s.ev===null?'—':format(s.isam-s.ev));set('gen-isam',format(s.genIsam));set('gen-ev',format(s.genEv));set('gen-delta',s.genEv===null?'—':format(s.genIsam-s.genEv));set('status',s.status);set('gen-status',s.genStatus);set('outcome',s.outcome);}
 choice.addEventListener('change',render);render();
});
