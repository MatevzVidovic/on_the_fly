

Nov način coniranja: 

Željeno delovanje: 

1. Nov model iz nule: Nov prazen latest VM, brez vseh geometrij, se poveže z obstoječo VO (kjer je bil prejšnji latest model te vrste modela), in nato se lahko z območji povezujejo cone. 
    
    1. To je že mogoče s preprostim prestavljanjem VM na pravo VO. Bolje bi bilo, da se v splošnem prestavljanje onemogoči in za to naredi preprost workflow. 
        
2. Pridružitev na VO: Nek latest model (npr. latest PPP) lahko pridružimo na VO, ki je odklenjena (ima same latest modele). Imamo 3 scenarije za to, kaj se zgodi z geometrijami VM: 
    
    1. izberemo VM na ciljnem VO. Celotna veriga geometrij (cone, LAO, TAO) izbranega VM se kopira na geometrije VM, ki ga prestavljamo.  
        
        1. Če je število vrednostnih ravni ciljnega VM večje ali enako od števila vrednostnih ravni premikajočega VM, se številka vrednostne ravni na conah prav tako kopira. 
            
        2. Če ni, potem se na premikajočem VM vsem conam št. vrednostne ravni nastavi na 1. 
            
    2. Ni potrebna izbira VM na VO. Važno le, da smo izbrali odklenjen VO (s samimi latest modeli). Kopira se brez da bi se ustvarile katerekoli cone, LAO, TAO. 
        
    3. Dorazvoj: Ni potrebna izbira VM na VO. Važno le, da smo izbrali odklenjen VO (s samimi latest modeli). Ohranimo cone, LAO, TAO premikajočega modela. Povezave obmxcona se ustvarijo glede na geometrijski presek novih območij in premaknjenih con (opcije so ST_Contains, ST_Intersects, ali pa npr. da cona pokriva več kot npr. 51% ali 98% območja.) 
        
3. Kopiranje znotraj VO: V odklenjenem VO lahko med 2 prisotnima VM kopiramo geometrija na enaka opisana načina, kot se zgodi pri združevanju.  

TODO:

Ticket za preprečitev ročnega premikanja VM med VO. 

Ticket za SFC pridružitve, in za vsako od kopij verige VO. 

WF za pridružitev latest modela na odklenjen VO, kjer se pobrišejo vse obmxcone, ne pa ostala veriga. (reši se model iz nule in iniciacija pridruževanja) 

WF za 2.2 ko je znotraj VO (pobriše veriga obmxcone do TAO) 

WF za 2.1 ko je znotraj VO (najprej kliče in powaita 2.2 WF, potem kopira drug model