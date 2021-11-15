package main

import (
	 "fmt"
	 "time"
	 "testing"
       )

var size int
var stride int
var chunk int

func main() {
}

func dotest() int {
     size := 1024*1024*1024*2
     stride := 4*1024
     chunk  := 1024*512
     var a int
     x := make([]int, size)
    // var x [1024*1024*1024*8]int
     for j:=0; j<size; j++ {
       x[j] = 0
     }
     for  i:=0; i< stride; i++ {
	     for j:=0; j< chunk; j++ {
             a = x[j*4096+i]
       }
     }
     return a;
}


func TestSum(t *testing.T) {

     start1 := time.Now()
     dotest()
     end1 := time.Since(start1)
     fmt.Println(end1)
}
