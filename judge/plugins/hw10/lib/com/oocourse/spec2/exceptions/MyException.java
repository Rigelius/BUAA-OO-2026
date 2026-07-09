package com.oocourse.spec2.exceptions;

/** 所有业务异常的抽象基类，强制子类实现 print
 */
public abstract class MyException extends Exception {
    public abstract void print();
    
}