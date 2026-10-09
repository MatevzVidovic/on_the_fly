  
  

- zaklenjen: true ko vsebuje katerikoli model, ki NI najvišja številka verzije modela za to vrsto modela (v nadaljevanju: Latest). Potem se ne sme urejati.

- delovna geo coniranje - namen: vidljivost na karti. Delovanje: true mora biti, ko: vsebuje samo Latest modele + lahko vsebuje druge verzije modela, ki so iste vrste kot Latest modeli, ki jih vsebuje)

  

Naša pravila:

- če na VO obstaja Latest model za nek tip modela, morajo za vse ostale tipe modela na VO biti prisotni tudi Latest modeli tistega tipa.

- ko se kopira verzija območij, se naprej premaknejo natanko Latest modeli prejšnje VO.

  

Trenutno delovanje:

- ko kopiraš verzijo območij, se v novo verzijo premaknejo le Latest modeli, ki so na tej verziji območij. Prejšnja verzija območij se zaklene.

  
  

Kaj hočemo:

- Združevanje območij (neko VM daješ na nek drug verzija območij. Klikneš SFC za workflow z VM in VO ki jih hočeš. Naredi se kopija tiste VO, v obm_x_cone za VM se pa naredi prevezovanje: tale cona je prej imela tale geom. Tale obm iz nove VO so več kot 98% površine v tej coni, zato bodo imeli povezavo z njo.)

  

Naše pravilo:

Nikoli se ročno ne prevezuje verzij modela in verzije con.

  
  
  

Kaj mogoče rabimo:

- kopija z uporabo druge verzije območij (si recimo nekaj zafrknil pri latest verziji in bi rad resetiral na prejšno stabilno verzijo območij). Isto mora bit workflow, ker imaš VO ki imajo recimo 3 latest modele, in to se mora vse skupaj premikat. SFC da workflowu novo in staro VO. Ampak kako zaboga zdaj uparjat cone in obm? Ker če hočeš zadeve resetirat, potem si na gaometrijah con že nekaj zafrknil. Mogoče je treba skopirat in obm in cone, potem pa to geometrijsko povezovanje delat na: cona - LAO?

(ročno premikanje modela nazaj in potem kopiranje sploh ne more delat!