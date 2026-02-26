#import "@preview/finite:0.5.0": automaton


#automaton((
 idle: (addr:"1"),
  addr: (data:"ar.fire"),
  data: (idle: "r.last & r.fire"),
))




