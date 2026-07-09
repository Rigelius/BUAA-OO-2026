package com.oocourse.spec1.main;

public interface VideoInterface {
    /*@ public instance model int id;
      @ public instance model int uploaderId;
      @*/

    //@ ensures \result == id;
    public /*@ pure @*/ int getId();

    //@ ensures \result == uploaderId;
    public /*@ pure @*/ int getUploaderId();

    /*@ public normal_behavior
      @ requires obj != null && obj instanceof VideoInterface;
      @ assignable \nothing;
      @ ensures \result == (((VideoInterface) obj).getId() == id);
      @ also
      @ public normal_behavior
      @ requires obj == null || !(obj instanceof VideoInterface);
      @ assignable \nothing;
      @ ensures \result == false;
      @*/
    public /*@ pure @*/ boolean equals(Object obj);

}
