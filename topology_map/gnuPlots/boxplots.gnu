reset

set terminal svg size 1100,1200 enhanced font "Arial,18"
set output "boxplot.svg"

set encoding utf8

set title "Emission Difference (%)"
set xlabel "Hour of the Day"
set ylabel "Emission Difference (%) (SP-LE)"

set grid xtics ytics

set tmargin 3
set bmargin 9
set lmargin 10
set rmargin 3

set key below horizontal maxrows 1 font ",13" 
set key spacing 11

set xrange [-0.5:23.5]
set yrange [-0.4:5]
set xtics 0,2,22

set style fill transparent solid 0.35 border
set bars 0.5

# RUN FOR 2023-01-10 and 2023-07-10

do for [len=2:6] {
    set output sprintf("boxplot_len%d.svg", len)
    set title sprintf("Emission Difference (%%) - Length %d", len)
    set xlabel "Hour of the Day"
    set ylabel "Emission Difference (%) (SP-LE)"

   plot \
    sprintf("boxplot_data_len%d_2023-01-10.dat", len) \
    using 1:3:2:6:5 with candlesticks whiskerbars lc rgb "black" title "5-95% whiskers", \
    "" using 1:7 with points pt 13 ps 0.8 lc rgb "forest-green" title "Mean", \
    "" using 1:4 with lines lc rgb "orange" lw 2 title "Median", \
    sprintf("alldata_len%d_2023-01-10.dat", len) using 1:2 with points pt 7 ps 0.5 lc rgb "black" notitle, \
}

unset output