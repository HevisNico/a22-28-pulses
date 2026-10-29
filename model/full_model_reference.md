# Modèle complet de référence — réalisation hybride R

> **Statut au 18 octobre 2026, après audit.** Ce document reprend la définition physique du dossier antérieur, sans modifier ses lois. La section 7 rapporte les résultats historiques de ces archives ; elle ne les requalifie pas comme validés par le noyau corrigé. Les corrections locales de conversion exacte et de différence temporelle ont été testées ; aucun rejeu global avec ces corrections n'est annoncé. L'identité physique des atomes, les collisions de jetons et la composition hybride complète restent à examiner. La campagne principale demeure en pause.

Ce document décrit la réalisation hybride alimentée effectivement calculée. Il ne définit pas « R minimal » et ne déduit ni le graphe, ni les couplages, ni les sources d'énergie depuis une théorie plus primitive. Les unités de charge et de temps sont celles du circuit idéal.

## 1. Graphe, source, paramètres

Le graphe comporte 18 couches dirigées de 12 voies périodiques. La cellule (n,j) reçoit, dans l'ordre des ports 0,1,2, les émissions de (n−1,j−1), (n−1,j), (n−1,j+1), indices modulo 12. La couche source n=0 est extérieure : seule sa voie 0 émet. Les contacts ont un délai nul ; les temps de réponse et de récupération appartiennent aux unités. Les couplages et la géométrie sont fournis.

Un feu à F produit le courant canonique

\[
p_F(t)=a e^{-a(t-F)}\mathbf 1_{[F,F+1)}(t),\qquad a=\ln4.
\]

Chaque port porte au plus un pulse à la fois dans la classe traitée. Le protocole d'amorçage est exactement 128 pulses aux dates 8k, k=0,…,127, suivi d'une observation à T=1116. La classe de continuation future consiste en pulses canoniques de cette même source, séparés d'au moins 20, à partir de la section terminale. Les mots temporels sont les listes d'intervalles entre ces pulses ; il ne s'agit pas de courants arbitraires.

Constantes principales : κ=1/2, r=1/10, r_m=1/40, seuils principaux et auxiliaires égaux à 1, butée b_max=11/10, gains initiaux nominaux (3/10,6/5,3/10), récupération nominale b_0=2/25.

Pour chaque port, les constantes auxiliaires et sa butée de gain sont fixes dans le temps, indépendamment choisies dans les intervalles relatifs ±ε des valeurs nominales :

\[
C=4,\quad L_m=\ln(5/4)/(1/50),\quad
L_s=\ln8/(53/50),\quad L_e=\ln4/(3/20),
\]
\[
h(u)=\frac{a}{a-\kappa}(e^{-\kappa u}-e^{-au}),\qquad
M=\frac{1-r_m}{h(1/50)}.
\]

La notation C, L_m, L_s, L_e, M dans le programme désigne les boîtes communes qui encadrent ces paramètres indépendants ; elle n'impose pas l'égalité des réalisations entre ports. Les paramètres a, κ, r, r_m, les gains d'actuation 8 et 1/2, le pompage et la butée b_max ne sont pas perturbés dans cette famille.

## 2. État physique et lois principales

Une cellule possède q, trois charges auxiliaires m_i, trois dépôts logarithmiques z_i (g_i=e^{z_i}), b, une réserve E, un mode principal P∈{prêt, rapide, lent}, un mode auxiliaire H_i∈{prêt, marque, silencieux, erreur} par port, et les courants entrants/sortants encore actifs. Les registres informatiques d'intégrales, origines temporelles et contraintes d'ordre représentent cet état et son histoire causale ; ils ne sont pas des capteurs physiques supplémentaires.

En mode prêt, l'admission principale est ouverte :

\[
\dot q=\kappa(r-q)+\sum_i g_i p_i(t).
\]

Au premier franchissement ascendant de q=1, q est fixé à 1, l'admission ferme et le mode rapide commence. Il satisfait q̇=−a q et émet p_F pendant exactement une unité de temps. À q=1/4, l'émission utile cesse et le mode lent satisfait

\[
\dot q=-b(t)q.
\]

La réouverture est le franchissement descendant q=r ; le mode prêt reprend à q=r exactement. Il n'y a pas de calendrier de récupération prescrit. La phase rapide et la phase lente ont les mêmes portes d'admission et d'actuation.

## 3. Frontière auxiliaire et plasticité

L'auxiliaire i voit le courant brut de son port même lorsque la principale est protégée. Prêt, il satisfait ṁ_i=κ(r_m−m_i)+M_i p_i. Son premier franchissement ascendant de 1 lance successivement :

| Mode | Équation | Section de sortie | Courant utile |
| --- | --- | --- | --- |
| Marque | ṁ_i=−L_{m,i}m_i | 4/5 | v_{m,i}=L_{m,i}m_i |
| Silencieux | ṁ_i=−L_{s,i}m_i | 1/10 | 0 |
| Erreur différée | ṁ_i=−L_{e,i}m_i | r_m | v_{e,i}=L_{e,i}m_i |

À chaque section, la charge atteint exactement la valeur indiquée et le mode change ; à r_m l'auxiliaire redevient prêt. Au nominal, les frontières ont les âges .02, .04, 1.10, 1.25 par rapport à l'arrivée. En dehors du nominal, les dates sont produites par ces équations, et non réglées à ces valeurs.

Lorsque E>0, les actuations sont

\[
\dot z_i=8v_{e,i}\mathbf1_{P=\mathrm{prêt}}\mathbf1_{z_i<\ln C_i},
\qquad
\dot b=\tfrac12\sum_i v_{m,i}\mathbf1_{P\ne\mathrm{prêt}}\mathbf1_{b<1.1}.
\]

Elles s'annulent à E=0 et sont projetées exactement sur les butées atteintes. Elles sont monotones. Une section entière d'erreur reçue porte ouverte offre Δz=8(.1−.025)=.6 ; une marque entière reçue sous protection offre Δb=(1−.8)/2=.1. Une réception partielle conserve l'intégrale de ses vrais endpoints, pas une fraction temporelle choisie après coup.

Le circuit ne consulte ni cible de vitesse, ni compteur d'émissions, ni indicateur logiciel « échec ». Le courant différé est un dispositif physique qui peut encore arriver quand l'admission a rouvert ; il ne constitue pas un détecteur universel de l'absence de relais.

## 4. Ressource

\[
\dot E=10(100-E)-\mathcal W.
\]

Avec coefficients de coût unité, W est la somme : courant admis par la principale si prête, a q si rapide ou coût de veille 1.1 si lente ; courants M_i p_i admis par les auxiliaires prêts ; drains L_{H_i,i}m_i des auxiliaires protégés ; mouvements effectifs Σż_i+ḃ. Chaque terme est non négatif. Cette convention de travail et le pompage sont des données du modèle, sans prétention à une dérivation microscopique.

Les bornes paramétriques du programme donnent

\[
\mathcal W\le (3C+3M+1)a+1.1+4.5L_m+2.4L_e<270<500.
\]

À E=50, Ė>0 ; à E=100, Ė≤0. Ainsi [50,100] est invariant pour toute réserve initiale dans cet intervalle. Les portes de puissance restent ouvertes. Le vérificateur utilise cette preuve analytique uniforme, plutôt que d'intégrer une réserve ponctuelle ou de substituer un minimum échantillonné.

## 5. Boîte initiale complète et réduction initiale

Pour chaque cellule, indépendamment : P prêt ; q∈[r−δ,r+δ] ; z_i∈[ln(g_{i,nom})−δ,ln(g_{i,nom})+δ] ; b∈[.08−δ,.08+δ] ; E∈[50,100]. Chaque auxiliaire est soit prêt, m_i∈[r_m−δ,r_m+δ], soit en fin de sa phase d'erreur, m_i∈[r_m,r_m+δ]. On n'autorise pas ici des phases auxiliaires arbitraires au milieu de leur cycle. Aucun pulse antérieur ou courant différé supplémentaire n'est caché dans l'état initial ; seules ces fins de phase et l'entrée source à t=0 sont présentes.

Le programme encadre d'abord une petite tranche U_0=2δ/(L_e r_m), choisie avec arrondi extérieur. Toute fin de phase initiale y est achevée. La charge principale est encadrée par r+[-δ,δ]exp(−κU_0)+[0,3CaU_0] ; les dépôts par ln(g_nom)+[−δ,9δ] couvrent les contributions résiduelles d'erreur. Le premier délai sensoriel est encadré séparément (`D1`), les suivants depuis r_m (`D0`). Les inégalités de `settings` vérifient la séparation des sections et les bornes de travail. Cette réduction est un surencadrement de la boîte annoncée, pas une réinitialisation physique.

Les deux campagnes distinguées sont δ=ε=10^−42 et δ=10^−5, ε=10^−4. Aucun changement de rayon n'est permis dans une reprise large.

## 6. Sémantique événementielle et domaine d'application

Les seuils sont les premiers franchissements dans le mode concerné. Les états continus restent continus aux arrivées extérieures ; seuls modes et portes changent, avec les resets de section indiqués. Les contacts de butée sont des projections monotones, pas des violations à éviter.

La sémantique ensembliste déclarée exige, lorsque les encadrements ne fixent pas un ordre, de couvrir tous les ordres non stricts compatibles avec les automates ; des égalités peuvent appartenir à plusieurs linéarisations à durée nulle. Aucune priorité physique ne découle d'un tri flottant. La garantie recherchée porte sur ce surensemble de continuations, donc sur les conventions de simultanéité représentées par ces linéarisations. Le modèle ne fournit pas de priorité totale universelle ; aucune autre règle de collision, de reset discontinu ou de pulse fusionné n'est implicitement autorisée. La couverture effective de chaque chemin du code demeure une obligation de l'audit, et ne découle pas de cette déclaration.

Les lemmes de frontière supposent que le cycle sensoriel est fini avant la prochaine arrivée du même port. Les émetteurs principaux vérifient l'interfeu minimal 1+ln(2.5)/1.1>1.83299, et les cycles auxiliaires ont durée <1.3 dans la famille. La source est plus espacée. Les files extérieures doivent contenir toutes les six frontières de chaque pulse utile ; les racines non isolables et les budgets dépassés entraînent un refus.

## 7. Énoncés rapportés dans les archives, avec leurs quantificateurs

1. **Continuation locale.** Si l'état initial et la file satisfont les conditions de `PREUVE_CONTINUATION.md`, toutes les trajectoires admissibles représentées sont contenues dans la réunion des branches retournées. Chaque branche conserve son état et ses propres émissions. Des branches irréalisables peuvent subsister ; l'existence de chaque branche n'est pas affirmée.
2. **Réseau étroit.** Pour la famille δ=ε=10^−42, le rejeu final A20 part de l'état initial, termine les 18 couches à T=1116 et compose l'entrée complète avec un domaine futur invariant. Il contient 21 302 feux ; 191 unités actives sont au repos exact, quatre ports sont en butée. Le coefficient propre à ce domaine étroit est Q12≈.6246369142769641<.625.
3. **Préfixe large.** Pour δ=10^−5, ε=10^−4, les dix premières couches ont une inclusion terminale et un domaine futur invariant vérifiés. Les 82 histoires de (10,2) et les 86 de (10,10) restent séparées avec leurs émissions. Les états actifs sont au repos exact, les auxiliaires ont fini, les courants différés et sortants ont fini et E∈[50,100]. Le domaine futur concerne la source canonique espacée d'au moins 20.

Dans chacun de ces domaines, la même onde entrante retrouve les mêmes gains, la charge prête r et les mêmes équations de tête : les dates de sortie sont les dates de source plus des retards fixes pour un dispositif fixé. Les intervalles successifs du mot sont donc conservés sur les unités actives. La récupération b peut rester plastique tant que les marges uniformes garantissent le retour avant l'apport suivant. Une perturbation de charge prête non remise à r n'a pas cette fidélité exacte dès sa première réponse.

**Non acquis :** la fermeture large 11–18, son mélange sur 12 couches, un front asymptotique commun, un coût d'accès borné pour plusieurs préparations spatiales, une vitesse universelle, ou la nécessité de ce mécanisme dans tout R minimal. Les premiers calculs A22 ne font pas partie du résultat livré ici. Une preuve écrite et des calculs validés ne constituent pas une vérification formelle du programme par un assistant de preuve indépendant.

## 8. Précision du domaine du lemme de translation

Pour une réalisation physique fixée θ et une cohorte de ports actifs J, on définit

\[
L_t(\theta)=\min_{j\in J}t_j(\theta),\qquad
U_t(\theta)=\min_{j\in J}(t_j(\theta)+1),\qquad
D_t(\theta)=[L_t(\theta),U_t(\theta)).
\]

Avant le premier feu, si la cellule est READY exactement à r, sans mémoire de courant, et si les mêmes gains physiques restent fixes, la charge sur cette portion est

\[
q_t(v,\theta)=r+\sum_{j\in J}g_j(\theta)h_+(v-t_j(\theta)),
\]

avec h_+(u)=0 pour u≤0 et h_+(u)=h(u) pour 0<u<1. Le franchissement pertinent est le premier passage ascendant au seuil 1 dans D_t, supposé exister avant toute fin d'impulsion.

Si s_j=t_j+d pour une constante exacte d et pour tous les ports, D_s=D_t+d et les charges correspondantes se translatent. Leurs premiers franchissements se translatent alors ; l'unicité de tous les zéros ultérieurs n'est pas nécessaire. Cela suppose les mêmes paramètres physiques et une formule de charge valable jusqu'au franchissement. Une égalité de boîtes de gains ou de dates ne remplace pas ces hypothèses.

Le feu exactement à une fin d'impulsion n'est pas couvert par ce lemme de tête. Une garde simultanée, une fenêtre absolue ou un autre filtre nécessite son propre traitement. Le lemme ne décide pas l'état après une simultanéité et ne prouve ni la continuation hybride ni l'invariance future à lui seul.

## 9. Provenance et limites de ce document

La définition physique des sections 1–5 provient de `MODELE_ET_PROPRIETE.md` du dossier d'audit antérieur. La section 6 précise son statut de sémantique déclarée ; la section 8 explicite la portion admise demandée par l'audit. Aucun paramètre physique ni rayon initial n'a été changé pour cette mise à disposition. Les faits numériques de la section 7 sont des résultats historiques rapportés, soumis à l'examen des obligations d'implémentation ouvertes.

Les corrections et les pièces de code sont dans `R_audit_IA_A22.zip` et son supplément `R_code_audit_A22.zip`. Le vérificateur hybride corrigé refuse Python `-O/-OO`, car le noyau hérité utilise encore des assertions comme obligations de preuve. Les tests arithmétiques isolés sous `-O` ne constituent pas une validation du noyau hybride dans ce mode.
