

int: nb_programs;
int: nb_days;
int: budget;

array[1..nb_programs] of int: durations;  % en créneaux de 30 min
array[1..nb_programs] of int: costs;
array[1..nb_programs] of int: audiences;
array[1..nb_programs] of int: genres;
% 1=Journal 2=Météo 3=Documentaire 4=Film 5=Série 6=Emission 7=Sport
array[1..nb_programs] of int: ad_revenues;
array[1..nb_programs] of int: profits;

int: slots_per_day;
int: max_duration;
array[1..nb_programs] of int: fixed_day;

int: idx_jt13;  % index 1-based du JT 13h dans la liste
int: idx_jt20;  % index 1-based du JT 20h dans la liste



array[1..nb_days, 1..nb_programs] of var 0..1: x;



array[1..nb_days] of var 0..slots_per_day: used_slots;

constraint forall(d in 1..nb_days)(
  used_slots[d] = sum(p in 1..nb_programs)( x[d,p] * durations[p] )
);



% C1 : au moins 34 créneaux par jour (= 17h minimum, quasi-plein)
%      L'égalité stricte = 36 est un bin-packing NP-difficile avec des films 4-7 créneaux.
%      34 garantit des journées quasi-complètes tout en restant faisable.
constraint forall(d in 1..nb_days)(
  used_slots[d] >= 34
);

% C2 : budget journalier = budget hebdo / 7
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs)( x[d,p] * costs[p] ) <= budget div nb_days
);

% C3 : chaque programme passe au max 1 fois par semaine
%      exceptions : JT 13h, JT 20h (tous les jours)
%                   programmes de 1 créneau (bouche-trous réutilisables : météo, flash)
constraint forall(p in 1..nb_programs where p != idx_jt13 /\ p != idx_jt20
                                       /\ durations[p] > 1)(
  sum(d in 1..nb_days)( x[d,p] ) <= 1
);

% C5 : quotas par genre par jour
%   - Journal  : max 2 créneaux hors JT fixes (1 JT optionnel suffit)
%   - Autres genres principaux : max 12 créneaux (~33%) pour la diversité
int: max_slots_journal  = 2;   % 1 JT optionnel max (30-60min)
int: max_slots_genre    = 12;  % ~33% de 36 créneaux pour les autres genres

% Journal (genre 1) — très limité hors JT fixes
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 1 /\ p != idx_jt13 /\ p != idx_jt20)(
    x[d,p] * durations[p]
  ) <= max_slots_journal
);

% Film (genre 4)
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 4)( x[d,p] * durations[p] ) <= max_slots_genre
);

% Série (genre 5)
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 5)( x[d,p] * durations[p] ) <= max_slots_genre
);

% Documentaire (genre 3)
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 3)( x[d,p] * durations[p] ) <= max_slots_genre
);

% Emission (genre 6)
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 6)( x[d,p] * durations[p] ) <= max_slots_genre
);

% Sport (genre 7)
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 7)( x[d,p] * durations[p] ) <= max_slots_genre
);

% C7 : au moins 1 programme de chaque genre clé par jour
%      (Film, Série, Documentaire, Emission, Sport)
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 4)( x[d,p] ) >= 1  % Film
);
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 5)( x[d,p] ) >= 1  % Série
);
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 3)( x[d,p] ) >= 1  % Documentaire
);
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 6)( x[d,p] ) >= 1  % Emission
);
constraint forall(d in 1..nb_days)(
  sum(p in 1..nb_programs where genres[p] = 7)( x[d,p] ) >= 1  % Sport
);


constraint forall(d in 1..nb_days)( x[d, idx_jt13] = 1 );
constraint forall(d in 1..nb_days)( x[d, idx_jt20] = 1 );




% Priorité 1 : maximiser le remplissage (chaque créneau vaut 1 000 000)
% Priorité 2 : maximiser le profit à remplissage égal
var int: slots_used_total = sum(d in 1..nb_days)( used_slots[d] );
var int: profit_total =
  sum(d in 1..nb_days, p in 1..nb_programs)( x[d,p] * profits[p] );

solve maximize slots_used_total * 1000000 + profit_total;



output [
  "Jour \(d) : \(fix(used_slots[d])) créneaux | "
  ++ show(sum(p in 1..nb_programs)( fix(x[d,p]) * costs[p] )) ++ " € | "
  ++ "J=" ++ show(sum(p in 1..nb_programs where genres[p]=1)(fix(x[d,p])*durations[p]))
  ++ " F=" ++ show(sum(p in 1..nb_programs where genres[p]=4)(fix(x[d,p])*durations[p]))
  ++ " S=" ++ show(sum(p in 1..nb_programs where genres[p]=5)(fix(x[d,p])*durations[p]))
  ++ " D=" ++ show(sum(p in 1..nb_programs where genres[p]=3)(fix(x[d,p])*durations[p]))
  ++ " M=" ++ show(sum(p in 1..nb_programs where genres[p]=6)(fix(x[d,p])*durations[p]))
  ++ " Sp=" ++ show(sum(p in 1..nb_programs where genres[p]=7)(fix(x[d,p])*durations[p]))
  ++ "\n"
  | d in 1..nb_days
];
