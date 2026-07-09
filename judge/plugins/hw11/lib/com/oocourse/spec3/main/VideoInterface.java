package com.oocourse.spec3.main;

public interface VideoInterface {

    /*@ public instance model int id;
      @ public instance model int uploaderId;
      @ public instance model non_null String type;
      @ public instance model int playCount;
      @ public instance model int likes;
      @ public instance model int forwardCount;
      @ public instance model int coins;
      @ public instance model non_null int[] commentIds;
      @ public instance model non_null String[] commentContents;
      @*/

    /*@ invariant commentIds.length == commentContents.length &&
      @  (\forall int i,j; 0 <= i && i < j && j < commentIds.length;
      @     commentIds[i] != commentIds[j])
      @*/

    //@ ensures \result == id;
    public /*@ pure @*/ int getId();

    //@ ensures \result == uploaderId;
    public /*@ pure @*/ int getUploaderId();

    //@ ensures \result == type;
    public /*@ pure @*/ String getType();
    
    //@ ensures \result == playCount;
    public /*@ pure @*/ int getPlayCount();

    //@ ensures \result == likes;
    public /*@ pure @*/ int getLikes();

    //@ ensures \result == forwardCount;
    public /*@ pure @*/ int getForwardCount();

    //@ ensures \result == coins;
    public /*@ pure @*/ int getCoins();

    //@ ensures \result == playCount * 2 + likes * 3 + forwardCount * 4 + coins * 5;
    public /*@ pure @*/ int getHeat();

    //@ ensures \result == (\exists int i; 0 <= i && i < commentIds.length; commentIds[i] == id);
    public /*@ pure @*/ boolean containsComment(int id);

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
    public boolean equals(Object obj);
}